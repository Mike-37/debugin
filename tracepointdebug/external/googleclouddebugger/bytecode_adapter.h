#pragma once
#include <cstdint>
#include <vector>

struct Instruction {
  uint8_t opcode;
  int32_t argument;
  int32_t size;
};

class IBytecodeAdapter {
public:
  virtual ~IBytecodeAdapter() = default;
  virtual Instruction Read(const std::vector<uint8_t>& bc, size_t off) const = 0;
  virtual void Write(std::vector<uint8_t>& bc, size_t off, const Instruction&) const = 0;
  virtual bool HasArg(uint8_t opcode) const = 0;
  virtual bool IsBranchDelta(uint8_t opcode) const = 0;
  virtual int32_t BranchTarget(int32_t off, const Instruction&) const = 0;
};