#ifndef __REACHING_DEFINITIONS__
#define __REACHING_DEFINITIONS__

#include "llvm/IR/Function.h"
#include "llvm/IR/InstIterator.h"
#include "llvm/Pass.h"
#include "llvm/Support/raw_ostream.h"

#include <fstream>
#include "dataflow.h"
#include "utils.h"

#include <stdio.h>
#include <stdlib.h>
#include <sys/time.h>
#include <time.h>

namespace llvm {

//////////////////////////////////////////////////////////////////////////////////////////////
//Dataflow analysis
class ReachingDefinitionsDataFlow : public DataFlow {
   protected:
    BitVector applyMeet(std::vector<BitVector>& meetInputs);

    TransferResult applyTransfer(const BitVector& value, DenseMap<Value*, int>& domainEntryToValueIdx, BasicBlock* block);
};
//////////////////////////////////////////////////////////////////////////////////////////////

class ReachingDefinitions : public ModulePass {
   public:
    static char ID;
    std::set<std::string> TargetFunc;

    std::map<std::string, std::map<Value*, std::vector<Value*> > > func_reaching_def;
    std::map<std::string, std::map<Value*, BasicBlock*> > func_instr_bb_map;
    std::map<std::string, std::map<BasicBlock*, std::string> > func_bb_name_map;
    std::map<std::string, std::map<Value*, int> > func_instr_id_map;

    ReachingDefinitions() : ModulePass(ID) {}

    //Find reaching defintions of operands
    void getOperandDefVals(Instruction* inst, std::map<Value*, std::vector<Value*> >& reaching_def_instr, std::map<Value*, BasicBlock*>& instr_bb_map, std::map<BasicBlock*, std::string>& bb_name_map, std::map<Value*, int>& instr_id_map);

    virtual bool doInitialization(Module& M);

    virtual bool doFinalization(Module& M);

    bool runOnFunction(Function& F);
    bool runOnModule(Module& M);

    virtual void getAnalysisUsage(AnalysisUsage& AU) const {
        AU.setPreservesAll();
    }

   private:
};

}  // namespace llvm

#endif
