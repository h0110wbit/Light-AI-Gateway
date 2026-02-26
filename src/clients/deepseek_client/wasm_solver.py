"""
DeepSeek WASM挑战求解器

使用wasmtime库加载和调用原项目的WASM模块进行挑战求解
"""
import wasmtime
import struct
from typing import Optional


class DeepSeekWasmSolver:
    """DeepSeek WASM挑战求解器"""

    def __init__(self, wasm_path: str):
        """
        初始化WASM求解器
        
        Args:
            wasm_path: WASM文件路径
        """
        self.wasm_path = wasm_path
        self.store = None
        self.instance = None
        self.memory = None
        self._initialized = False
        # 缓存TextEncoder
        self._cached_text_encoder = None
        self._cached_uint8_memory = None
        self._offset = 0

    async def init(self) -> None:
        """初始化WASM模块"""
        try:
            # 创建wasmtime引擎和存储
            engine = wasmtime.Engine()
            self.store = wasmtime.Store(engine)

            # 加载WASM模块
            module = wasmtime.Module.from_file(engine, self.wasm_path)

            # 实例化模块
            self.instance = wasmtime.Instance(self.store, module, [])

            # 获取内存引用
            self.memory = self.instance.exports(self.store)["memory"]

            self._initialized = True

        except Exception as e:
            raise RuntimeError(f"初始化WASM求解器失败: {e}")

    def _get_cached_uint8_memory(self) -> memoryview:
        """
        获取WASM内存视图
        
        Returns:
            内存视图
        """
        if self._cached_uint8_memory is None:
            self._cached_uint8_memory = self.memory.data_ptr(self.store)
        return self._cached_uint8_memory

    def _encode_string(self, text: str) -> int:
        """
        编码字符串到WASM内存
        
        参考原项目的编码逻辑，处理ASCII和非ASCII字符
        
        Args:
            text: 要编码的字符串
            
        Returns:
            内存指针
        """
        if not self._initialized:
            raise RuntimeError("WASM求解器未初始化")

        # 获取分配和重新分配函数
        alloc_func = self.instance.exports(
            self.store).get("__wbindgen_export_0")
        realloc_func = self.instance.exports(
            self.store).get("__wbindgen_export_1")

        if not alloc_func:
            raise RuntimeError("未找到内存分配函数")

        str_length = len(text)

        # 如果没有重新分配函数，使用简单编码
        if not realloc_func:
            encoded = text.encode('utf-8')
            ptr = alloc_func(self.store, len(encoded), 1)
            memory = self._get_cached_uint8_memory()
            memory_slice = memory[ptr:ptr + len(encoded)]
            for i, byte in enumerate(encoded):
                memory_slice[i] = byte
            self._offset = len(encoded)
            return ptr

        # 复杂情况：分两步处理ASCII和非ASCII字符
        ptr = alloc_func(self.store, str_length, 1)
        memory = self._get_cached_uint8_memory()
        ascii_length = 0

        # 首先尝试ASCII编码
        for i in range(str_length):
            char_code = ord(text[i])
            if char_code > 127:
                break
            memory[ptr + i] = char_code
            ascii_length += 1

        # 如果存在非ASCII字符，需要重新分配空间并处理
        if ascii_length != str_length:
            remaining_text = text[ascii_length:] if ascii_length > 0 else text

            # 为非ASCII字符重新分配空间（每个字符最多需要3字节）
            new_size = ascii_length + len(remaining_text) * 3
            ptr = realloc_func(self.store, ptr, str_length, new_size, 1)

            # 编码剩余的非ASCII字符
            encoded_remaining = remaining_text.encode('utf-8')
            memory = self._get_cached_uint8_memory()
            for i, byte in enumerate(encoded_remaining):
                memory[ptr + ascii_length + i] = byte

            written = len(encoded_remaining)
            ascii_length += written

            # 最终调整内存大小
            ptr = realloc_func(self.store, ptr, new_size, ascii_length, 1)

        self._offset = ascii_length
        return ptr

    def calculate_hash(self, algorithm: str, challenge: str, salt: str,
                       difficulty: int, expire_at: int) -> Optional[int]:
        """
        计算挑战答案
        
        Args:
            algorithm: 算法名称
            challenge: 挑战字符串
            salt: 盐值
            difficulty: 难度
            expire_at: 过期时间
            
        Returns:
            答案值，如果求解失败返回None
        """
        if not self._initialized:
            raise RuntimeError("WASM求解器未初始化")

        if algorithm != 'DeepSeekHashV1':
            raise ValueError(f"不支持的算法: {algorithm}")

        try:
            # 拼接前缀
            prefix = f"{salt}_{expire_at}_"

            # 获取栈指针调整函数
            add_to_stack = self.instance.exports(
                self.store).get("__wbindgen_add_to_stack_pointer")
            if not add_to_stack:
                raise RuntimeError("未找到栈指针调整函数")

            # 分配栈空间（16字节用于返回结果）
            retptr = add_to_stack(self.store, -16)

            # 编码字符串参数
            ptr0 = self._encode_string(challenge)
            len0 = self._offset

            ptr1 = self._encode_string(prefix)
            len1 = self._offset

            # 获取求解函数
            solve_func = self.instance.exports(self.store).get("wasm_solve")
            if not solve_func:
                raise RuntimeError("未找到wasm_solve函数")

            # 调用求解函数（difficulty需要作为浮点数传入）
            solve_func(self.store, retptr, ptr0, len0, ptr1, len1,
                       float(difficulty))

            # 读取返回结果
            memory = self._get_cached_uint8_memory()

            # 读取状态（4字节整数，小端序）
            status_bytes = bytes(memory[retptr:retptr + 4])
            status = int.from_bytes(status_bytes, 'little', signed=True)

            # 读取值（8字节浮点数，小端序）
            value_bytes = bytes(memory[retptr + 8:retptr + 16])
            value = struct.unpack('<d', value_bytes)[0]

            # 释放栈空间
            add_to_stack(self.store, 16)

            # 如果求解失败，返回None
            if status == 0:
                return None

            return int(value)

        except Exception as e:
            print(f"WASM求解失败: {e}")
            return None


# 全局WASM求解器实例
_wasm_solver: Optional[DeepSeekWasmSolver] = None


async def get_wasm_solver(wasm_path: str) -> DeepSeekWasmSolver:
    """
    获取全局WASM求解器实例
    
    Args:
        wasm_path: WASM文件路径
        
    Returns:
        WASM求解器实例
    """
    global _wasm_solver

    if _wasm_solver is None:
        _wasm_solver = DeepSeekWasmSolver(wasm_path)
        await _wasm_solver.init()

    return _wasm_solver
