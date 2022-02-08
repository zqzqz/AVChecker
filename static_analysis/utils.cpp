#include "utils.h"
#include <cxxabi.h>
#include <memory>
#include <string>
#include "llvm/IR/Instructions.h"

namespace llvm {

std::string demangle(const char *name) {
    int status = -1;

    std::unique_ptr<char, void (*)(void *)> res{abi::__cxa_demangle(name, NULL, NULL, &status), std::free};
    return (status == 0) ? res.get() : std::string(name);
}

std::string get_func_name(const char *name){
    std::string func_name = demangle(name);
    if (func_name.find("(") == std::string::npos) return func_name;
    int bracket_index = std::string(func_name).find("(");
    int count = 0;
    std::string pruned_str;
    for (size_t i = 0; i < bracket_index; i++)
    {
        if (func_name[i] == '<') count++;
        if (count == 0) pruned_str += func_name[i];
        if (func_name[i] == '>') count--;
    }
    return pruned_str;
}

bool std_function(const char *name) {

    std::string func_name = get_func_name(name);

    if (func_name.find("apollo::") != std::string::npos) return false;
    if (func_name.find("double") != std::string::npos) return false;
    if (func_name.find("__gnu_cxx::") != std::string::npos) return true;
    if (func_name.find("std::") != std::string::npos) return true;
    if (func_name.find("verbose_level") != std::string::npos) return true;
    if (func_name.find("Iterator") != std::string::npos) return true;
    return false;
}

Value *valueToDefVar(Value *v) {
    if (isa<Argument>(v)) {
        return v;
    } else if (isa<StoreInst>(v)) {
        return ((StoreInst *)v)->getPointerOperand();
    } else if (isa<BitCastInst>(v)) {
        return ((BitCastInst *)v)->getOperand(0);
    } else if (isa<Instruction>(v)) {
        if (dyn_cast<Instruction>(v)->getType()->isVoidTy())
            return nullptr;
        else
            return v;
    } else {
        return nullptr;
    }
}

std::string typeToStr(Type* t) {
    std::string type_str;
    raw_string_ostream rso(type_str);
    t->print(rso);
    return rso.str();
}

std::string beautyFuncName(Function *F) {
    std::string name = demangle(F->getName().str().c_str());
    name = name.substr(0, name.find_first_of("("));
    name = name.substr(0, name.find_first_of("<"));
    name = name.substr(name.find_last_of("::") + 1);
    return name;
}

Function *getCalledFunction(CallBase *call) {
    Function *func = call->getCalledFunction();
    if (func == nullptr) {
        Value *tmp = call->getCalledValue()->stripPointerCasts();
        if (isa<Function>(tmp)) {
            func = dyn_cast<Function>(tmp);
        }
    }
    return func;
}

std::string getTypeName(Value *V) {
    // get type name
    std::string local_name;
    llvm::raw_string_ostream rso(local_name);
    V->getType()->print(rso);
    std::string temp_name = rso.str();
    auto start = temp_name.find_first_of("\"");
    auto end = temp_name.find_last_of("\"");
    if (start != std::string::npos && end != std::string::npos && end > start) {
        temp_name = temp_name.substr(start+1, end-start-1);
    }
    // fix redundant prefix
    if (temp_name.find("class") == 0) {
        temp_name = temp_name.substr(5);
    }
    if (temp_name.find(".") == 0) {
        temp_name = temp_name.substr(1);
    }
    return temp_name;
}

bool isVectorType(Value *V) {
    std::string typeName = getTypeName(V);
    if (typeName.find("std::vector") != std::string::npos ||
        typeName.find("google::protobuf::RepeatedPtrField") != std::string::npos) {
        return true;
    } else {
        return false;
    }
}

}  // namespace llvm