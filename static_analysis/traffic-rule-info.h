#ifndef __TRAFFIC_RULE_INFO_H__
#define __TRAFFIC_RULE_INFO_H__

#include "control-dependency.h"
#include "utils.h"

#include "llvm/Analysis/LoopInfo.h"
#include "llvm/Analysis/PostDominators.h"
#include "llvm/IR/Function.h"
#include "llvm/IR/Module.h"
#include "llvm/Pass.h"
#include <llvm/Support/raw_ostream.h>

// Option 1: use KLEE to directly perform module level symbolic execution
// #include "klee/klee.h"

// Option 2: Use z3 as our theorem solver to perform a simple symbolic execution
#include "z3++.h"

#include <map>
#include <vector>
#include <sstream> 

namespace llvm {

class VectorStatus {
  public:
    // vector analysis
    std::map<Value *, std::set<Value *>> vectorTaints;
    std::set<Value *> vectorSources;
    std::map<Value *, bool> vectorStatus;

    VectorStatus() {}
    VectorStatus(VectorStatus const &other) {
        vectorTaints = other.vectorTaints;
        vectorSources = other.vectorSources;
        vectorStatus = other.vectorStatus;
    }

    void setSources(std::set<Value *> vectors);
    void setSource(Value *vec, bool status);
    void propagate(Instruction *I, Instruction *def);
    Value *tainted(Instruction *I);
    bool getStatus(Value *vec);
    void setStatus(Value *vec, bool status);
    bool operator==(const VectorStatus &other) {
        return vectorStatus == other.vectorStatus;
    }
};

class Path {
   public:

    // vector analysis
    VectorStatus vectorStatus;
    // z3 expr has no default constructors...
    z3::expr *constraint;
    std::map<Instruction *, z3::expr *> vars;
    std::vector<MNode *> nodes;
    std::vector<BasicBlock *> blocks;
    Function *F;
    BasicBlock *next;
    unsigned int weight = 1;

    Path(Function *F, z3::context &c) : F(F) {
        constraint = new z3::expr(c.bool_val(true));
        next = &(F->getEntryBlock());
    }

    Path(Path const &other) {
        vectorStatus = VectorStatus(other.vectorStatus);
        constraint = other.constraint;
        nodes = other.nodes;
        blocks = other.blocks;
        vars = other.vars;
        F = other.F;
        next = other.next;
        weight = other.weight;
    }

    bool operator==(const Path &other) {
        return F == other.F && next == other.next && vars == other.vars && vectorStatus == other.vectorStatus;
    }
};

class TrafficRuleInfo : public ModulePass {
   public:
    static char ID;

    // func => path[]
    std::map<Function *, std::vector<Path>> funcPaths;
    // func => return expr,
    std::map<Function *, z3::expr *> returnExprs;
    // callee => caller => constraint
    std::map<Function *, std::map<Function *, z3::expr *>> funcConstraints;
    // global var map
    std::map<Value *, z3::expr *> globalVars;
    // final result
    z3::expr *result;
    // global constraints among z3 expressions
    std::vector<z3::expr *> globalConstraints;
    // func => value => z3 expr
    std::map<Value*, z3::expr*> hardcode;
    std::set<std::string> apiFuncName;

    unsigned int path_cnt = 1;

    // depracated!
    // // func => return expr => constraint,
    // std::map<Function *, std::map<z3::expr *, z3::expr *>> returnMultiExprs;

    std::set<BasicBlock *> extendedBlocks;

    static unsigned unnamedVarCnt;

    TrafficRuleInfo() : ModulePass(ID) {}
    bool runOnFunction(Function &F, ControlDependency &CD, z3::context &c);
    bool runOnModule(Module &M);
    virtual bool doInitialization(Module &M);
    virtual bool doFinalization(Module &M);
    
    virtual void getAnalysisUsage(AnalysisUsage &AU) const {
        // add dependencies here
        AU.addRequired<ControlDependency>();
        AU.addRequired<LoopInfoWrapperPass>();
        AU.addRequired<DominatorTreeWrapperPass>();
        // AU.setPreservesAll();
    }

   private:
    void extractConstraint(ControlDependency &CD, z3::context &c);

    void extendPaths(Function *F, BasicBlock *BB, std::set<EdgeType> edges, MNode *N, ControlDependency &CD, z3::context &c);
    void finalizePaths(Function *F, ControlDependency &CD, z3::context &c);
    void printPaths(Function *F);
    void mergePaths(Function *F);
    void cleanPaths(Function *F, z3::context &c);

    void executeBlock(Path *P, MNode *N, ControlDependency &CD, z3::context &c);
    void executeBranch(Path *P, MNode *N, BasicBlock *next, ControlDependency &CD, z3::context &c);
    void executeInstruction(Path *P, MNode *N, Instruction *I, ControlDependency &CD, z3::context &c);

    z3::expr *newZ3Const(Constant *C, z3::context &c);
    z3::expr *newZ3DefaultConst(Type *T, z3::context &c);
    z3::expr *newZ3Var(Value *V, ControlDependency &CD, z3::context &c);
    z3::expr *getZ3Expr(Path *P, Instruction *def);
    std::string getVarName(Value *V, ControlDependency &CD);

    void initRetExprs(ControlDependency &CD, z3::context &c);

    std::string valueToStr(const Value *value);
    std::string getValDefVar(const Value *def);
    std::string getPredicateName(CmpInst::Predicate Pred);
    std::string getOpType(Value *I, std::string operand);
    Instruction *getUniqueDefinition(Path *P, MNode *N, Instruction *I, Value *V);

    void getHardcodeMap(Module &M, ControlDependency &CD, z3::context &c) {
        for (auto &gvar : M.getGlobalList()) {
            if (gvar.getName() == "_ZN6apollo8planning12CreepDecider20creep_clear_counter_E") {
                hardcode[&gvar] = new z3::expr(c.int_val(4));
            }
        }
        for (Function *F : CD.TargetFuncPtrs) {
            std::string funcName = demangle(F->getName().str().c_str());
            if (funcName.find("apollo::planning::Crosswalk::MakeDecisions") != std::string::npos ) {
                for (BasicBlock &BB : *F) {
                    for (Instruction &I : BB) {
                        if (isa<CallBase>(&I)) {
                            Function* calledFunc = getCalledFunction(dyn_cast<CallBase>(&I));
                            std::string calledFuncName = demangle(calledFunc->getName().str().c_str());
                            if (calledFuncName.find("has_crosswalk_id") != std::string::npos) {
                                hardcode[&I] = new z3::expr(c.bool_val(false));
                            }
                            if (calledFuncName.find("_ZSteqIcEN9__gnu_cxx11__enable_ifIXsr9__is_charIT_EE7__valueEbE6__typeERKSbIS2_St11char_traitsIS2_ESaIS2_EESA_") != std::string::npos) {
                                hardcode[&I] = new z3::expr(c.bool_val(false));
                            }
                            if (calledFuncName.find("hypot") != std::string::npos) {
                                hardcode[&I] = new z3::expr(c.real_val(1));
                            }
                        }
                    }
                }
            }
            if (funcName.find("apollo::planning::TrafficLight::MakeDecisions") != std::string::npos ||
                funcName.find("apollo::planning::StopSign::MakeDecisions") != std::string::npos) {
                for (BasicBlock &BB : *F) {
                    for (Instruction &I : BB) {
                        if (isa<CallBase>(&I)) {
                            Function* calledFunc = getCalledFunction(dyn_cast<CallBase>(&I));
                            std::string calledFuncName = demangle(calledFunc->getName().str().c_str());
                            if (calledFuncName.find("_ZSteqIcEN9__gnu_cxx11__enable_ifIXsr9__is_charIT_EE7__valueEbE6__typeERKSbIS2_St11char_traitsIS2_ESaIS2_EESA_") != std::string::npos) {
                                hardcode[&I] = new z3::expr(c.bool_val(false));
                            }
                        }
                    }
                }
            }
            if (funcName.find("apollo::planning::Crosswalk::CheckStopForObstacle") != std::string::npos) {
                for (BasicBlock &BB : *F) {
                    for (Instruction &I : BB) {
                        if (isa<CallBase>(&I)) {
                            Function* calledFunc = getCalledFunction(dyn_cast<CallBase>(&I));
                            std::string calledFuncName = demangle(calledFunc->getName().str().c_str());
                            if (calledFuncName.find("apollo::perception::PerceptionObstacle::type") != std::string::npos) {
                                hardcode[&I] = new z3::expr(c.real_val(1));
                            }
                        }
                    }
                }
            }
            if (funcName.find("apollo::planning::scenario::stop_sign::StopSignUnprotectedStagePreStop::AddWatchVehicle") != std::string::npos ||
                funcName.find("apollo::planning::scenario::stop_sign::StopSignUnprotectedStageStop::RemoveWatchVehicle") != std::string::npos) {
                for (BasicBlock &BB : *F) {
                    for (Instruction &I : BB) {
                        if (isa<CallBase>(&I)) {
                            Function* calledFunc = getCalledFunction(dyn_cast<CallBase>(&I));
                            std::string calledFuncName = calledFunc->getName().str().c_str();
                            if (calledFuncName.find("_ZN9__gnu_cxxeqIPSt4pairISt10shared_ptrIKN6apollo5hdmap8LaneInfoEES2_IKNS4_11OverlapInfoEEESt6vectorISB_SaISB_EEEEbRKNS_17__normal_iteratorIT_T0_EESL_") != std::string::npos) {
                                hardcode[&I] = new z3::expr(c.bool_val(false));
                            }
                            if (calledFuncName.find("_ZSteqIKN6apollo5hdmap8LaneInfoEEbRKSt10shared_ptrIT_EDn") != std::string::npos) {
                                hardcode[&I] = new z3::expr(c.bool_val(false));
                            }
                            if (calledFuncName.find("_ZN9__gnu_cxxeqIPSsSt6vectorISsSaISsEEEEbRKNS_17__normal_iteratorIT_T0_EESA_") != std::string::npos) {
                                hardcode[&I] = new z3::expr(c.bool_val(true));
                            }
                        }
                    }
                }
            }
            if (funcName.find("apollo::planning::SpeedDecider::MakeObjectDecision") != std::string::npos) {
                for (BasicBlock &BB : *F) {
                    for (Instruction &I : BB) {
                        if (isa<CallBase>(&I)) {
                            Function* calledFunc = getCalledFunction(dyn_cast<CallBase>(&I));
                            if (calledFunc->getName().str().find("_ZNKSt6vectorIN6apollo6common10SpeedPointESaIS2_EE4sizeEv") != std::string::npos) {
                                hardcode[&I] = new z3::expr(c.real_val(4));
                            }
                        }
                    }
                }
            }
        }
    }

    void getApiFuncName() {
        apiFuncName.insert("apollo::common::math::Polygon2d::IsPointIn(apollo::common::math::Vec2d const&) const");
    }
};

}  // namespace llvm

#endif  // __TRAFFIC_RULE_INFO_H__