// 15-745 S14 Assignment 2: dataflow.h
// Group: bhumbers, psuresh
////////////////////////////////////////////////////////////////////////////////

#ifndef __CLASSICAL_DATAFLOW_DATAFLOW_H__
#define __CLASSICAL_DATAFLOW_DATAFLOW_H__

#include <stdio.h>

#include "llvm/ADT/BitVector.h"
#include "llvm/ADT/DenseMap.h"
#include "llvm/ADT/SmallSet.h"
#include "llvm/IR/CFG.h"
#include "llvm/IR/Instructions.h"
#include "llvm/IR/ValueMap.h"

#include <vector>

namespace llvm {

struct DataFlowResult;

/** Returns the variable that is defined by the given value (argument, instruction, etc.), 
* or null if the given value is not a definition */
Value* getDefinitionVar(Value* v);

bool hasDefinition(Value* v);

Value* valueToDefinitionVar(Value* v);

void valueToAllDefinitionVar(Value* v, std::vector<Value*>& def_var, std::vector<std::string>& def_field);

std::string getCallee(Value* v);

Value* getCalleeArg(Value* v, int i);

std::string loadFuncRD(std::string func);

void setFuncRD(std::string func, std::vector<std::string>& idx);

void getBBReachDef(DenseMap<Value*, int>& domainEntryToValueIdx, BasicBlock* block, int instr_limit, std::map<Value*, std::map<Value*, std::set<std::string> > >& def_set);

// Generate function summary
void getFuncRedef(Function& F, std::vector<Value*>& domain, DataFlowResult& dataFlowResult);

/** Util to create string representation of given BitVector */
std::string bitVectorToStr(const BitVector& bv);

/** Util to output string representation of an llvm Value */
std::string valueToStr(const Value* value);

std::string typeToString(Type* t);

/** Returns string representation of a set of domain elements with inclusion indicated by a bit vector
 Each element is output according to the given valFormatFunc function */
std::string setToStr(std::vector<Value*>& domain, const BitVector& includedInSet, std::string (*valFormatFunc)(Value*));

/** Returns string version of definition if the Value is in fact a definition, or an empty string otherwise.
 * eg: The defining instruction "%a = add nsw i32 %b, 1" will return exactly that: "%a = add nsw i32 %b, 1"*/
std::string valueToDefinitionStr(Value* v);

/** Returns the name of a defined variable if the given Value is a definition, or an empty string otherwise.
 * eg: The defining instruction "%a = add nsw i32 %b, 1" will return "a"*/
std::string valueToDefinitionVarStr(Value* v);

/** An intermediate transfer function output entry from a block. In addition to the main value,
 * may include a list of predecessor block-specific transfer values which are appended (unioned)
 * onto the main value for the meet operator input of each predecessor (used to handle SSA phi nodes) */
struct TransferResult {
    BitVector baseValue;
    DenseMap<BasicBlock*, BitVector> predSpecificValues;
};

struct ReachingDef {
    Value* op_def;
    std::string op_field;
    int op_idx;
};

struct DataFlowResultForBlock {
    //Final output
    BitVector in;
    BitVector out;

    //Intermediate results
    TransferResult currTransferResult;

    DataFlowResultForBlock() {}
    DataFlowResultForBlock(BitVector in, BitVector out) {
        this->in = in;
        this->out = out;
        this->currTransferResult.baseValue = out;  //tra
    }
};

struct DataFlowResult {
    /** Mapping from domain entries to linear indices into value results from dataflow */
    DenseMap<Value*, int> domainEntryToValueIdx;

    /** Mapping from basic blocks to the IN and OUT value sets for each after analysis converges */
    DenseMap<BasicBlock*, DataFlowResultForBlock> resultsByBlock;
};

/** Base interface for running dataflow analysis passes.
 * Must be subclassed with pass-specific logic in order to be used.
*/
class DataFlow {
   public:
    enum Direction {
        FORWARD,
        BACKWARD
    };

    /** Run this dataflow analysis on function using given parameters.*/
    DataFlowResult run(Function& F,
                       std::vector<Value*>& domain,
                       Direction direction,
                       BitVector boundaryCond,
                       BitVector initInteriorCond, std::set<BasicBlock*>& prune_bb);

    /** Prints a representation of F to raw_ostream O. */
    void ExampleFunctionPrinter(raw_ostream& O, const Function& F);

    void PrintInstructionOps(raw_ostream& O, const Instruction* I);

   protected:
    /** Meet operator behavior; specific to the subclassing data flow */
    virtual BitVector applyMeet(std::vector<BitVector>& meetInputs) = 0;

    /** Transfer function behavior; specific to a subclassing data flow
     * domainEntryToValueIdx provides mapping from domain elements to the linear bitvector index for that element. */
    virtual TransferResult applyTransfer(const BitVector& value, DenseMap<Value*, int>& domainEntryToValueIdx, BasicBlock* block) = 0;
};

}  // namespace llvm

#endif
