#include "bytecode_adapter.h"
#include "common.h"
#include <algorithm>

// Implementation for Python <= 3.10, wrapping existing logic
class BytecodeAdapter310 : public IBytecodeAdapter {
public:
    Instruction Read(const std::vector<uint8_t>& bytecode,
                     size_t offset) const override {
        // This is a simplified version - in a real implementation, we'd need to 
        // properly extract the logic from the existing bytecode_manipulator.cc
        Instruction instruction { 0, 0, 0 };
        
#if PY_MAJOR_VERSION >= 3
        if (bytecode.size() - offset < 2) {
            return { 0, 0, 0 }; // Invalid instruction
        }

        size_t current_pos = offset;
        uint32_t argument = 0;
        int size = 0;

        // Handle EXTENDED_ARG opcodes
        while (current_pos < bytecode.size() && bytecode[current_pos] == EXTENDED_ARG) {
            argument = argument << 8 | bytecode[current_pos + 1];
            current_pos += 2;
            size += 2;
            
            if (bytecode.size() - current_pos < 2) {
                return { 0, 0, 0 }; // Invalid instruction
            }
        }

        instruction.opcode = bytecode[current_pos];
        argument = argument << 8 | bytecode[current_pos + 1];
        size += 2;
        instruction.argument = argument;
        instruction.size = size;
#else
        if (offset >= bytecode.size()) {
            return { 0, 0, 0 }; // Invalid instruction
        }

        instruction.opcode = bytecode[offset];
        instruction.size = 1;

        if (HAS_ARG(instruction.opcode)) {
            if (offset + 2 >= bytecode.size()) {
                return { 0, 0, 0 }; // Invalid instruction
            }
            
            instruction.argument = bytecode[offset + 1] | (bytecode[offset + 2] << 8);
            instruction.size = 3;
        }
#endif

        return instruction;
    }

    void Write(std::vector<uint8_t>& bytecode, size_t offset, 
               const Instruction& instruction) const override {
        // This is a simplified version - in a real implementation, we'd need to 
        // properly extract the logic from the existing bytecode_manipulator.cc
#if PY_MAJOR_VERSION >= 3
        uint32_t arg = instruction.argument;
        int size_written = 0;
        // Start writing backwards from the real instruction, followed by any
        // EXTENDED_ARG instructions if needed.
        for (int i = instruction.size - 2; i >= 0; i -= 2) {
            bytecode[offset + i] = size_written == 0 ? instruction.opcode : EXTENDED_ARG;
            bytecode[offset + i + 1] = static_cast<uint8_t>(arg);
            arg = arg >> 8;
            size_written += 2;
        }
#else
        bytecode[offset] = instruction.opcode;

        if (HAS_ARG(instruction.opcode)) {
            bytecode[offset + 1] = static_cast<uint8_t>(instruction.argument);
            bytecode[offset + 2] = static_cast<uint8_t>(instruction.argument >> 8);
        }
#endif
    }

    bool HasArg(uint8_t opcode) const override {
        return HAS_ARG(opcode);
    }

    bool IsBranchDelta(uint8_t opcode) const override {
        switch (opcode) {
            case FOR_ITER:
            case JUMP_FORWARD:
#if PY_VERSION_HEX < 0x0308000
            // Removed in Python 3.8.
            case SETUP_LOOP:
            case SETUP_EXCEPT:
#endif
            case SETUP_FINALLY:
            case SETUP_WITH:
#if PY_VERSION_HEX >= 0x03080000 && PY_VERSION_HEX < 0x03090000
            // Added in Python 3.8 and removed in 3.9
            case CALL_FINALLY:
#endif
                return true;

            default:
                return false;
        }
    }

    int32_t BranchTarget(int32_t offset, const Instruction& instruction) const override {
        if (IsBranchDelta(instruction.opcode)) {
            return offset + instruction.size + instruction.argument;
        } else {
            return instruction.argument;
        }
    }
};

// Factory function to create the appropriate adapter
IBytecodeAdapter* CreateBytecodeAdapter() {
    // Dispatch by interpreter version; 3.11+ path behind an env flag for now
    #if PY_VERSION_HEX >= 0x030B0000
      const char* exp = std::getenv("NATIVE_ADAPTER_EXPERIMENTAL");
      if (exp && std::string(exp) == "1") {
        // TODO: return new BytecodeAdapter311();  // when implemented
        return new BytecodeAdapter310(); // placeholder – keep behavior stable
      }
      // Default stable behavior: use 3.10 adapter until 3.11+ is ready
      return new BytecodeAdapter310();
    #else
      return new BytecodeAdapter310();
    #endif
}