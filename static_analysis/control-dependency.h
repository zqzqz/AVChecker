#ifndef __CONTROL_DEPENDENCY_H__
#define __CONTROL_DEPENDENCY_H__

#include "llvm/ADT/Statistic.h"
#include "llvm/IR/BasicBlock.h"
#include "llvm/IR/Function.h"
#include "llvm/IR/Instruction.h"
#include "llvm/Pass.h"
#include "llvm/Support/Debug.h"
#include "llvm/Support/raw_ostream.h"

#include <cxxabi.h>
#include <sys/stat.h>
#include <stack>
#include <unordered_map>
#include <unordered_set>
#include <vector>

#include <algorithm>
#include <fstream>

#include "llvm/Analysis/CFG.h"
#include "llvm/Analysis/CFGPrinter.h"
#include "llvm/Analysis/CallGraph.h"
// #include "llvm/Analysis/MemoryDependenceAnalysis.h"
#include "llvm/Analysis/LoopInfo.h"
#include "llvm/Analysis/PostDominators.h"

#include "reaching-definitions.h"
#include "utils.h"

#define DEBUG_TYPE "CD"

namespace llvm {

enum EdgeType {
    TRUE,
    FALSE,
    INVOKE_TRUE,
    INVOKE_FALSE,
    UNKNOWN
};

class MNode {
   public:
    BasicBlock *BB;
    std::set<EdgeType> edges;
    std::set<Instruction *> instrs;
    std::map<Instruction *, std::set<std::pair<Instruction *, Value *>>> DUs;
    std::map<std::pair<Instruction *, Value *>, std::set<Instruction *>> UDs;
    MNode(BasicBlock *BB) : BB(BB) {}
    void addEdges(EdgeType E) {
        edges.insert(E);
    }
    void addInstr(Instruction *I) {
        instrs.insert(I);
    }
    void addDU(Instruction *I, Instruction *VI, Value *V) {
        if (DUs.find(I) == DUs.end()) {
            DUs[I] = std::set<std::pair<Instruction *, Value *>>();
        }
        DUs[I].insert(std::make_pair(VI, V));
    }
    void addUD(Instruction *VI, Value *V, Instruction *I) {
        auto VP = std::make_pair(VI, V);
        if (UDs.find(VP) == UDs.end()) {
            UDs[VP] = std::set<Instruction *>();
        }
        UDs[VP].insert(I);
    }
    bool isInstrs(Instruction *I) {
        return instrs.find(I) != instrs.end();
    }
};

class CDNode {
   public:
    BasicBlock *from;
    BasicBlock *to;
    EdgeType E;
    CDNode(BasicBlock *from, BasicBlock *to, EdgeType E) : from(from), to(to), E(E) {}
};

class SinkBBNode {
   public:
    BasicBlock *BB;
    Instruction *I;
    Function *from;
    Function *to;
    SinkBBNode(BasicBlock *BB, Instruction *I, Function *from, Function *to) : BB(BB), I(I), from(from), to(to) {}
};

class ControlDependency : public ModulePass {
   public:
    static char ID;
    std::set<std::string> TargetFuncs;
    std::set<Function *> TargetFuncPtrs;
    // Target Functions
    std::set<std::string> TargetSinks;
    std::set<Function *> TargetSinkPtrs;
    // Source Functions
    std::set<std::string> TargetSources;
    std::set<Function *> TargetSourcePtrs;
    // Sink Information for given function
    std::map<Function *, std::vector<SinkBBNode *>> FunctionData;
    // Collection of critical BBs
    std::map<Function *, std::vector<MNode *>> MCFG;
    // Simplified call graph
    std::vector<std::vector<Function *>> CallChains;
    // Internal functions (not in call graph but essential)
    std::map<Instruction *, Function *> InterCalls;
    // alias caused by getelementptr
    std::map<Value *, std::set<Value *>> Alias;
    // vector dependencies: function => push_back
    std::map<Function *, std::set<Instruction *>> VectorDeps;
    std::map<Function *, std::set<std::pair<Value *, bool>>> VectorSources;

    unsigned int instr_cnt = 0;
    unsigned int instr_total = 0;
    unsigned int bb_cnt = 0;
    unsigned int bb_total = 0;
    unsigned int path_cnt = 1;

    // deprecated
    std::map<std::string, std::map<SinkBBNode *, std::vector<CDNode *>>> CDInfo;

    ControlDependency() : ModulePass(ID) {}

    virtual bool doInitialization(Module &M);

    virtual bool doFinalization(Module &M);

    bool runOnFunction(Function &F);

    bool runOnModule(Module &M);

    EdgeType getEdgeType(const BasicBlock *A, const BasicBlock *BB);
    SinkBBNode *getSinkBBNode(Function *F, BasicBlock *BB);
    MNode *getMNode(Function *F, BasicBlock *BB);
    std::set<Instruction *> getDefinitions(Function *F, Instruction *I, Value *val);

    virtual void getAnalysisUsage(AnalysisUsage &AU) const {
        AU.addRequired<PostDominatorTreeWrapperPass>();
        AU.addRequired<LoopInfoWrapperPass>();
        AU.addRequired<ReachingDefinitions>();
        AU.addRequired<CallGraphWrapperPass>();
        // AU.addRequired<MemoryDependenceWrapperPass>();
        // AU.setPreservesAll();
    }

   private:
    void initVectorDeps(Module &M);
    void initAlias(Module &M);
    void buildCallGraph(Module &M);
    void buildCallGraph(Module *M, CallGraph *CG);
};

}  // namespace llvm

#endif  // __CONTROL_DEPENDENCY_H__
