#include "reaching-definitions.h"
#include "llvm/IR/Function.h"
#include "llvm/IR/Module.h"
#include "llvm/Pass.h"

namespace llvm {

char ReachingDefinitions::ID = 2;
static RegisterPass<ReachingDefinitions> B("cd-reaching-definitions", "Reaching Definitions", false, true);

//////////////////////////////////////////////////////////////////////////////////////////////
//Dataflow analysis

BitVector ReachingDefinitionsDataFlow::applyMeet(std::vector<BitVector>& meetInputs) {
    BitVector meetResult;

    //Meet op = union of inputs
    if (!meetInputs.empty()) {
        for (int i = 0; i < meetInputs.size(); i++) {
            if (i == 0)
                meetResult = meetInputs[i];
            else
                meetResult |= meetInputs[i];
        }
    }

    return meetResult;
}

TransferResult ReachingDefinitionsDataFlow::applyTransfer(const BitVector& value, DenseMap<Value*, int>& domainEntryToValueIdx, BasicBlock* block) {
    TransferResult transfer;

    //First, calculate the set of downwards exposed definition generations and the set of killed definitions in this block
    int domainSize = domainEntryToValueIdx.size();
    BitVector genSet(domainSize);
    BitVector killSet(domainSize);

    int instr_cnt = 0;
    for (BasicBlock::iterator instruction = block->begin(); instruction != block->end(); ++instruction, instr_cnt++) {
        //std::string instr = valueToStr(&*instruction);
        //if (instr.find("  call void @llvm.dbg.declare") == 0) continue;
        DenseMap<Value*, int>::const_iterator currDefIter = domainEntryToValueIdx.find(&*instruction);
        if (currDefIter != domainEntryToValueIdx.end()) {
            //          errs() << "applyTransfer " << instr << "\n";
            //Kill prior definitions for the same variable (including those in this block's gen set)
            std::map<Value*, std::map<Value*, std::set<std::string> > > def_set;
            getBBReachDef(domainEntryToValueIdx, block, instr_cnt, def_set);
            for (DenseMap<Value*, int>::const_iterator prevDefIter = domainEntryToValueIdx.begin();
                 prevDefIter != domainEntryToValueIdx.end();
                 ++prevDefIter) {
                if (def_set.find(prevDefIter->first) == def_set.end()) {
                    killSet.set(prevDefIter->second);
                    genSet.reset(prevDefIter->second);
                }
            }

            //Add this new definition to gen set (note that we might later remove it if another def in this block kills it)
            genSet.set((*currDefIter).second);
        }
    }

    //Then, apply transfer function: Y = GenSet \union (X - KillSet)
    transfer.baseValue = killSet;
    transfer.baseValue.flip();
    transfer.baseValue &= value;
    transfer.baseValue |= genSet;

    return transfer;
}

//Find reaching defintions of operands
void ReachingDefinitions::getOperandDefVals(Instruction* inst, std::map<Value*, std::vector<Value*> >& reaching_def_instr, std::map<Value*, BasicBlock*>& instr_bb_map, std::map<BasicBlock*, std::string>& bb_name_map, std::map<Value*, int>& instr_id_map) {
    for (int i = 0; i < inst->getNumOperands(); i++) {
        Value* val = inst->getOperand(i);
        if (!isa<Argument>(val) && !isa<Instruction>(val))
            continue;
        for (int j = 0; j < reaching_def_instr[inst].size(); j++) {
            std::vector<Value*> def_var;
            std::vector<std::string> def_field;
            valueToAllDefinitionVar(reaching_def_instr[inst][j], def_var, def_field);
            for (int k = 0; k < def_var.size(); k++)
                if (def_var[k] == val) {}
                    // curr_instr-operand,bb,line : rd-bb,line
                    // errs() << "Reaching Defs (" << i << "," << bb_name_map[instr_bb_map[inst]] << "," << instr_id_map[inst] << ") : " << bb_name_map[instr_bb_map[reaching_def_instr[inst][j]]] << "," << instr_id_map[reaching_def_instr[inst][j]] << def_field[k] << "\n";
            //errs() << "Reaching Defs (" << i << "," << bb_name_map[instr_bb_map[inst]] << "," << instr_id_map[inst] << ") : " << bb_name_map[instr_bb_map[reaching_def_instr[inst][j]]] << "," << instr_id_map[reaching_def_instr[inst][j]] << "\n";
        }
    }
}

bool ReachingDefinitions::runOnFunction(Function& F) {
    if (F.isDeclaration())
        return false;
    std::string func_name = demangle(F.getName().str().c_str());
    // if (TargetFunc.find(func_name) == TargetFunc.end())
    //     return;
    if (TargetFunc.find(func_name) == TargetFunc.end())
        return false;

    // errs() << "Found func " << func_name << "\n";

    std::set<BasicBlock*> prune_bb;
    struct timeval start, end;
    std::map<Value*, BasicBlock*> instr_bb_map;
    std::map<BasicBlock*, std::string> bb_name_map;
    std::map<Value*, int> instr_id_map;

    //Set domain as a vector of definitions instr in the function
    std::vector<Value*> domain;
    int arg_idx = 0;
    bb_name_map[NULL] = "arg";
    for (Function::arg_iterator arg = F.arg_begin(); arg != F.arg_end(); ++arg) {
        domain.push_back(arg);
        instr_id_map[&*arg] = arg_idx;
        instr_bb_map[&*arg] = NULL;
        arg_idx++;
    }
    for (Function::iterator basicBlock = F.begin(); basicBlock != F.end(); ++basicBlock)
        if ((&*basicBlock) != &(F.getEntryBlock()) && pred_begin(&*basicBlock) == pred_end(&*basicBlock))
            prune_bb.insert(&*basicBlock);
    for (Function::iterator basicBlock = F.begin(); basicBlock != F.end(); ++basicBlock) {
        if ((&*basicBlock) == &(F.getEntryBlock()) || prune_bb.find(&*basicBlock) != prune_bb.end())
            continue;
        bool pred_found = false;
        for (pred_iterator predBlock = pred_begin(&*basicBlock); predBlock != pred_end(&*basicBlock); ++predBlock) {
            if (prune_bb.find(*predBlock) == prune_bb.end()) {
                pred_found = true;
                break;
            }
        }
        if (!pred_found)
            prune_bb.insert(&*basicBlock);
    }
    for (Function::iterator basicBlock = F.begin(); basicBlock != F.end(); ++basicBlock) {
        if (prune_bb.find(&*basicBlock) != prune_bb.end())
            continue;
        bb_name_map[&*basicBlock] = basicBlock->getName();
        int instr_idx = 0;
        gettimeofday(&start, NULL);
        int curr_size = domain.size();
        for (BasicBlock::iterator instruction = basicBlock->begin(); instruction != basicBlock->end(); ++instruction) {
            std::vector<Value*> def_var;
            std::vector<std::string> def_field;
            valueToAllDefinitionVar(&*instruction, def_var, def_field);
            if (def_var.size() > 0) {
                domain.push_back(&*instruction);
            }
            instr_id_map[&*instruction] = instr_idx;
            instr_bb_map[&*instruction] = &*basicBlock;
            instr_idx++;
        }
        gettimeofday(&end, NULL);
        // errs() << "Found BB " << bb_name_map[&*basicBlock] << " " << ((end.tv_sec * 1000000 + end.tv_usec) - (start.tv_sec * 1000000 + start.tv_usec)) << " " << (domain.size() - curr_size) << "\n";
    }
    int numVars = domain.size();

    // errs() << "Found func " << func_name << " " << numVars << "\n";

    //List of reaching definitions at an instruction
    std::map<Value*, std::vector<Value*> > reaching_def_instr;

    //Set the initial boundary dataflow value to be the set of input argument definitions for this function
    BitVector boundaryCond(numVars, false);
    for (int i = 0; i < domain.size(); i++)
        if (isa<Argument>(domain[i]))
            boundaryCond.set(i);

    //Set interior initial dataflow values to be empty sets
    BitVector initInteriorCond(numVars, false);

    //Get dataflow values at IN and OUT points of each block
    ReachingDefinitionsDataFlow flow;
    DataFlowResult dataFlowResult = flow.run(F, domain, DataFlow::FORWARD, boundaryCond, initInteriorCond, prune_bb);

    //Then, extend those values into the interior points of each block, outputting the result along the way
    errs() << "* REACHING DEFINITIONS OUTPUT FOR FUNCTION: " << func_name << " \n";
    //    errs() << "Domain of values: " << setToStr(domain, BitVector(domain.size(), true), valueToDefinitionStr) << "\n";
    //    errs() << "Variables: "   << setToStr(domain, BitVector(domain.size(), true), valueToDefinitionVarStr) << "\n";

    //Print function header (in hacky way... look for "definition" keyword in full printed function, then print rest of that line only)
    //    std::string funcStr = valueToStr(&F);
    //    int funcHeaderStartIdx = funcStr.find("define");
    //    int funcHeaderEndIdx = funcStr.find('{', funcHeaderStartIdx + 1);
    //    errs() << funcStr.substr(funcHeaderStartIdx, funcHeaderEndIdx-funcHeaderStartIdx) << "\n";

    //Now, use dataflow results to output reaching definitions at program points within each block
    for (Function::iterator basicBlock = F.begin(); basicBlock != F.end(); ++basicBlock) {
        if (prune_bb.find(&*basicBlock) != prune_bb.end()) continue;
        DataFlowResultForBlock blockReachingDefVals = dataFlowResult.resultsByBlock[&*basicBlock];

        //Print just the header line of the block (in a hacky way... blocks start w/ newline, so look for first occurrence of newline beyond first char
        //      std::string basicBlockStr = valueToStr(basicBlock);
        //      errs() << basicBlockStr.substr(0, basicBlockStr.find(':', 1) + 1) << "\n";

        //Initialize reaching definitions at the start of the block
        BitVector reachingDefVals = blockReachingDefVals.in;

        std::vector<std::string> blockOutputLines;

        //Output reaching definitions at the IN point of this block (not strictly needed, but useful to see)
        //      blockOutputLines.push_back("\nReaching Defs (BB IN): " + setToStr(domain, reachingDefVals, valueToDefinitionStr) + "\n");

        //Iterate forward through instructions of the block, updating and outputting reaching defs
        int instr_cnt = 0;
        for (BasicBlock::iterator instruction = basicBlock->begin(); instruction != basicBlock->end(); ++instruction, instr_cnt++) {
            //Output the instruction contents
            //blockOutputLines.push_back(valueToStr(&*instruction));

            //        std::string instr = valueToStr(&*instruction);
            //        if (instr.find("  call void @llvm.dbg") == 0) continue;

            DenseMap<Value*, int>::const_iterator defIter;

            Value* currDefStr = valueToDefinitionVar(&*instruction);  //std::string currDefStr = valueToDefinitionVarStr(instruction);

            //Kill (unset) all existing defs for this variable
            std::map<Value*, std::map<Value*, std::set<std::string> > > def_set;
            getBBReachDef(dataFlowResult.domainEntryToValueIdx, &*basicBlock, instr_cnt, def_set);
            for (defIter = dataFlowResult.domainEntryToValueIdx.begin(); defIter != dataFlowResult.domainEntryToValueIdx.end(); ++defIter) {
                if (def_set.find(defIter->first) == def_set.end())
                    reachingDefVals.reset(defIter->second);
            }

            //Add this definition to the reaching set
            defIter = dataFlowResult.domainEntryToValueIdx.find(&*instruction);
            if (defIter != dataFlowResult.domainEntryToValueIdx.end())
                reachingDefVals.set((*defIter).second);

            //Output the set of reaching definitions at program point just past instruction
            //(but only if not a phi node... those aren't "real" instructions)
            if (!isa<PHINode>(instruction)) {
                reaching_def_instr[&*instruction] = std::vector<Value*>();
                for (int i = 0; i < domain.size(); i++)
                    if (reachingDefVals[i])
                        reaching_def_instr[&*instruction].push_back(domain[i]);
                //          errs() << "Curr instr: " << valueToStr(&*instruction) << "\n";
                getOperandDefVals(&*instruction, reaching_def_instr, instr_bb_map, bb_name_map, instr_id_map);
                //Debugging output
                //for (int i = 0; i < reaching_def_instr[&*instruction].size(); i++)
                //     errs() << "Reaching Defs: " << valueToStr(reaching_def_instr[&*instruction][i]) << "\n";
                //          blockOutputLines.push_back("\nReaching Defs (" + valueToStr(&*instruction) + ", " + std::to_string(reaching_def_instr[&*instruction].size()) + "): " + setToStr(domain, reachingDefVals, valueToDefinitionStr) + "\n");
            }
        }

        //Debugging output
        //for (std::vector<std::string>::iterator i = blockOutputLines.begin(); i < blockOutputLines.end(); ++i)
        //  errs() << *i << "\n";
    }
    getFuncRedef(F, domain, dataFlowResult);
    errs() << "* END REACHING DEFINITION OUTPUT FOR FUNCTION: " << func_name << "\n";

    for (std::map<Value*, std::vector<Value*> >::iterator it = reaching_def_instr.begin(); it != reaching_def_instr.end(); it++) {
        func_reaching_def[func_name][it->first] = std::vector<Value*>();
        for (int i = 0; i < it->second.size(); i++)
            func_reaching_def[func_name][it->first].push_back((it->second)[i]);
    }
    for (std::map<Value*, BasicBlock*>::iterator it = instr_bb_map.begin(); it != instr_bb_map.end(); it++)
        func_instr_bb_map[func_name][it->first] = it->second;
    for (std::map<BasicBlock*, std::string>::iterator it = bb_name_map.begin(); it != bb_name_map.end(); it++)
        func_bb_name_map[func_name][it->first] = it->second;
    for (std::map<Value*, int>::iterator it = instr_id_map.begin(); it != instr_id_map.end(); it++)
        func_instr_id_map[func_name][it->first] = it->second;

    return false;
}

bool ReachingDefinitions::runOnModule(Module &M) {
    for (Function &F: M) {
        runOnFunction(F);
    }
}

bool ReachingDefinitions::doInitialization(Module& M) {
    //record the function name
    std::string configPath = "";
    std::ifstream configfile("config.tmp");
    if (configfile.is_open()) {
        std::getline(configfile, configPath);
    }
    std::ifstream infile(configPath + "/func.meta");
    if (infile.is_open()) {
        std::string func;
        while (std::getline(infile, func))
            TargetFunc.insert(func);
        infile.close();
    }
    return false;
}

bool ReachingDefinitions::doFinalization(Module& M) {
    return false;
}

}  // namespace llvm
