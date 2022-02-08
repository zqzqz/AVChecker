#ifndef __UTILS_H__
#define __UTILS_H__

#include <string>
#include "llvm/IR/InstrTypes.h"
#include "llvm/IR/Value.h"
#include "llvm/IR/Function.h"
#include "llvm/IR/Instruction.h"

namespace llvm {

std::string demangle(const char *name);

std::string get_func_name(const char *name);

bool std_function(const char *name);

Value* valueToDefVar(Value* v);

std::string typeToStr(Type* t);

std::string beautyFuncName(Function *F);

Function *getCalledFunction(CallBase *call);

std::string getTypeName(Value *V);

bool isVectorType(Value *V);

}  // namespace llvm

#endif  // __UTILS_H__