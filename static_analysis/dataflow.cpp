// 15-745 S14 Assignment 2: dataflow.cpp
// Group: bhumbers, psuresh
////////////////////////////////////////////////////////////////////////////////

#include <fstream>
#include <set>
#include <sstream>

#include "dataflow.h"

#include "llvm/Support/raw_ostream.h"

namespace llvm {

/* Var definition util */
Value* getDefinitionVar(Value* v) {
    // Definitions are assumed to be one of:
    // 1) Function arguments
    // 2) Store instructions (2nd argument is the variable being (re)defined)
    // 3) Instructions that start with "  %" (note the 2x spaces)
    //      Note that this is a pretty brittle and hacky way to catch what seems the most common definition type in LLVM.
    //      Unfortunately, we couldn't figure a better way to catch all definitions otherwise, as cases like
    //      "%0" and "%1" don't show up  when using "getName()" to identify definition instructions.
    //      There's got to be a better way, though...

    if (isa<Argument>(v)) {
        return v;
    } else if (isa<StoreInst>(v)) {
        return ((StoreInst*)v)->getPointerOperand();
    } else if (isa<Instruction>(v)) {
        std::string str = valueToStr(v);
        const int VAR_NAME_START_IDX = 2;
        if (str.length() > VAR_NAME_START_IDX && str.substr(0, VAR_NAME_START_IDX + 1) == "  %")
            return v;
    }
    return 0;
}

/******************************************************************************************
 * String output utilities */
std::string bitVectorToStr(const BitVector& bv) {
    std::string str(bv.size(), '0');
    for (int i = 0; i < bv.size(); i++)
        str[i] = bv[i] ? '1' : '0';
    return str;
}

std::string valueToStr(const Value* value) {
    std::string instStr;
    llvm::raw_string_ostream rso(instStr);
    rso << *value;  //value->print(rso);
    return instStr;
}

std::string typeToString(Type* t) {
    std::string type_str;
    raw_string_ostream rso(type_str);
    t->print(rso);
    return rso.str();
}

const int VAR_NAME_START_IDX = 2;

std::string valueToDefinitionStr(Value* v) {
    //Verify it's a definition first
    Value* def = getDefinitionVar(v);
    if (def == 0)
        return "";

    std::string str = valueToStr(v);
    if (isa<Argument>(v)) {
        return str;
    } else {
        str = str.substr(VAR_NAME_START_IDX);
        return str;
    }

    return "";
}

std::string valueToDefinitionVarStr(Value* v) {
    //Similar to valueToDefinitionStr, but we return just the defined var rather than the whole definition

    Value* def = getDefinitionVar(v);
    if (def == 0)
        return "";

    if (isa<Argument>(def) || isa<StoreInst>(def)) {
        return "%" + def->getName().str();
    } else {
        std::string str = valueToStr(def);
        int varNameEndIdx = str.find(' ', VAR_NAME_START_IDX);
        str = str.substr(VAR_NAME_START_IDX, varNameEndIdx - VAR_NAME_START_IDX);
        return str;
    }
}

bool hasDefinition(Value* v) {
    if (isa<Argument>(v)) {
        return true;
    } else if (isa<StoreInst>(v)) {
        return true;
    } else if (isa<Instruction>(v)) {
        return !(dyn_cast<Instruction>(v)->getType()->isVoidTy());
    } else {
        return false;
    }
}

// Compute reaching def by iterating instructions within a BB until "instr_limit", store reaching def per instr in "def_set"
void getBBReachDef(DenseMap<Value*, int>& domainEntryToValueIdx, BasicBlock* block, int instr_limit, std::map<Value*, std::map<Value*, std::set<std::string> > >& def_set) {
    std::set<Value*> local_instr;
    std::map<Value*, std::set<std::string> > local_def;
    int instr_cnt = 0;
    // Get all def vars in current BB
    for (BasicBlock::iterator instruction = block->begin(); instruction != block->end(); ++instruction, instr_cnt++) {
        local_instr.insert(&*instruction);
        DenseMap<Value*, int>::const_iterator currDefIter = domainEntryToValueIdx.find(&*instruction);
        if (currDefIter != domainEntryToValueIdx.end()) {
            std::vector<Value*> def_var;
            std::vector<std::string> def_field;
            valueToAllDefinitionVar(currDefIter->first, def_var, def_field);
            if (def_var.size() == 0)
                continue;
            for (int i = 0; i < def_var.size(); i++)
                local_def[def_var[i]].insert(def_field[i]);
        }
        if (instr_cnt == instr_limit)
            break;
    }
    /* 
      std::string currDefStr = "";
      for (std::set<std::string>::iterator it = local_def.begin(); it != local_def.end(); ++it)
           currDefStr += (*it + ";");
      if (currDefStr != "")
          currDefStr = currDefStr.substr(0, currDefStr.length()-1);
      //errs() << "getBBReach: currDefStr " << currDefStr << "\n";
*/
    // Add reaching defs in other BBs
    for (DenseMap<Value*, int>::const_iterator prevDefIter = domainEntryToValueIdx.begin();
         prevDefIter != domainEntryToValueIdx.end();
         ++prevDefIter) {
        if (local_instr.find(prevDefIter->first) == local_instr.end()) {
            std::vector<Value*> def_var;
            std::vector<std::string> def_field;
            valueToAllDefinitionVar(prevDefIter->first, def_var, def_field);
            std::map<Value*, std::set<std::string> > dedup_def;
            for (int i = 0; i < def_var.size(); i++) {
                if (local_def.find(def_var[i]) == local_def.end())
                    dedup_def[def_var[i]].insert(def_field[i]);
                else if (local_def[def_var[i]].find(def_field[i]) == local_def[def_var[i]].end())
                    dedup_def[def_var[i]].insert(def_field[i]);
            }
            for (std::map<Value*, std::set<std::string> >::iterator it = dedup_def.begin(); it != dedup_def.end(); it++)
                for (auto def_f : it->second)
                    def_set[prevDefIter->first][it->first].insert(def_f);
            //std::string prevDefStr = valueToDefinitionVarStr(prevDefIter->first);
            //if (!includeDefVarWithField(prevDefStr, currDefStr))
            //    def_set.insert(std::pair<Value*, std::string>(prevDefIter->first, dedupDefVarWithField(prevDefStr, currDefStr)));
        }
    }
    //for (std::map<Value*, std::string>::iterator jt = def_set.begin(); jt != def_set.end(); jt++)
    //     errs() << "getBBReach: def_set " << valueToStr(jt->first) << "\t" << jt->second << "\n";
    // Add reaching defs in current BB
    instr_cnt = 0;
    for (BasicBlock::iterator instruction = block->begin(); instruction != block->end(); ++instruction, instr_cnt++) {
        DenseMap<Value*, int>::const_iterator currDefIter = domainEntryToValueIdx.find(&*instruction);
        if (currDefIter != domainEntryToValueIdx.end()) {
            std::vector<Value*> def_var;
            std::vector<std::string> def_field;
            valueToAllDefinitionVar(currDefIter->first, def_var, def_field);
            def_set[currDefIter->first] = std::map<Value*, std::set<std::string> >();
            for (int i = 0; i < def_var.size(); i++)
                def_set[currDefIter->first][def_var[i]].insert(def_field[i]);
            //std::string currDefStr = valueToDefinitionVarStr(currDefIter->first);
            //def_set.insert(std::pair<Value*, std::string>(currDefIter->first, currDefStr));
            for (BasicBlock::iterator prevInst = block->begin(); prevInst != instruction; ++prevInst) {
                DenseMap<Value*, int>::const_iterator prevDefIter = domainEntryToValueIdx.find(&*prevInst);
                if (prevDefIter != domainEntryToValueIdx.end() && def_set.find(prevDefIter->first) != def_set.end()) {
                    std::map<Value*, std::set<std::string> > dedup_def;
                    bool overlapped = false;
                    for (std::map<Value*, std::set<std::string> >::iterator it = def_set[prevDefIter->first].begin(); it != def_set[prevDefIter->first].end(); it++) {
                        if (def_set[currDefIter->first].find(it->first) == def_set[currDefIter->first].end()) {
                            for (auto def_f : it->second)
                                dedup_def[it->first].insert(def_f);
                        } else {
                            for (auto def_f : it->second) {
                                if (def_set[currDefIter->first][it->first].find(def_f) == def_set[currDefIter->first][it->first].end())
                                    dedup_def[it->first].insert(def_f);
                                else
                                    overlapped = true;
                            }
                        }
                    }
                    if (dedup_def.size() == 0) {
                        def_set.erase(prevDefIter->first);
                    } else if (overlapped) {
                        def_set[prevDefIter->first] = std::map<Value*, std::set<std::string> >();
                        for (std::map<Value*, std::set<std::string> >::iterator it = dedup_def.begin(); it != dedup_def.end(); it++)
                            for (auto def_f : it->second)
                                def_set[prevDefIter->first][it->first].insert(def_f);
                    }
                    //std::string prevDefStr = def_set[prevDefIter->first];
                    //if (includeDefVarWithField(prevDefStr, currDefStr))
                    //    def_set.erase(prevDefIter->first);
                    //else if (overlapDefVar(prevDefStr, currDefStr))
                    //    def_set[prevDefIter->first] = dedupDefVarWithField(prevDefStr, currDefStr);
                }
            }
        }
        if (instr_cnt == instr_limit)
            break;
    }
}

void getFuncRedef(Function& F, std::vector<Value*>& domain, DataFlowResult& dataFlowResult) {
    std::string func = F.getName().str();
    std::map<Value*, std::set<std::string> > arg_redef;
    for (Function::iterator basicBlock = F.begin(); basicBlock != F.end(); ++basicBlock) {
        if (succ_begin(&(*basicBlock)) == succ_end(&(*basicBlock))) {
            DataFlowResultForBlock blockReachingDefVals = dataFlowResult.resultsByBlock[&*basicBlock];
            BitVector reachingDefVals = blockReachingDefVals.out;
            // Extract def var from each instruction in RD set and check if it has been defined previously
            for (int i = 0; i < domain.size(); i++) {
                if (reachingDefVals[i]) {
                    //errs() << "Debug: " << valueToStr(domain[i]) << "," << domain[i]->getType()->isPointerTy() << "\n";
                    if (isa<Argument>(domain[i]))
                        continue;
                    std::vector<Value*> def_var;
                    std::vector<std::string> def_field;
                    valueToAllDefinitionVar(domain[i], def_var, def_field);
                    for (int j = 0; j < def_var.size(); j++)
                        if (isa<Argument>(def_var[j]) && domain[i]->getType()->isPointerTy())
                            arg_redef[def_var[j]].insert(def_field[j]);
                    /*               if (isa<Instruction>(domain[i])) {
                        Instruction *instr = dyn_cast<Instruction>(domain[i]);
                        // Assume def var through operand in store/call/invoke given SSA form
                        for (User::op_iterator it = instr->op_begin(), e = instr->op_end(); it != e; ++it) {
                             if (!isa<Instruction>(*it) && !isa<Argument>(*it))
                                 continue;
                             if (*it == instr)
                                 continue;
                             // Get overlap def var
                             std::vector<Value*> prev_def_var;
                             std::vector<std::string> prev_def_field;
                             valueToAllDefinitionVar(*it, prev_def_var, prev_def_field);
                             for (int j = 0; j < prev_def_var.size(); j++) {
                                  for (int jj = 0; jj < def_var.size(); jj++) {
                                       if (prev_def_var[j] == def_var[jj]) {
                                           if (prev_def_field[j] == def_field[jj])
                                               func_redef[def_var[jj]][def_field[jj]] = true;
                                           else if (prev_def_field[j] == "" && def_field[jj] != "")
                                               func_redef[def_var[jj]][def_field[jj]] = true;
                                           else if (prev_def_field[j] != "" && def_field[jj] == "")
                                               func_redef[prev_def_var[j]][prev_def_field[j]] = true;
                                           else if (prev_def_field[j].find(def_field[jj]) != std::string::npos)
                                               func_redef[def_var[jj]][def_field[jj]] = true;
                                           else if (def_field[jj].find(prev_def_field[j]) != std::string::npos)
                                               func_redef[prev_def_var[j]][prev_def_field[j]] = true;
                                       }
                                  }
                             }       
                        }
                    }*/
                }
            }
        }
    }
    /*    int i = 0;
    //Checking redef of func args
    for (Function::ArgumentListType::iterator arg = F.getArgumentList().begin(); arg != F.getArgumentList().end(); arg++) {
          std::string type_str = typeToString(arg->getType());
          std::string arg_str = argToString(&*arg);
          if (arg_str == type_str) {
              i++;
              continue;
          }
          std::string var_str = arg_str.substr(arg_str.find_last_of(" ")+1);
          if (type_str.substr(type_str.length()-1) == "*") {
              for (std::map<std::string, bool>::iterator it = func_redef[func].begin(); it != func_redef[func].end(); it++) {
                   if (!it->second)
                       continue;
                   if (it->first == var_str)
                       func_arg_rd[func].push_back(std::to_string(i));
                   //Checking field redef of func args
                   if (it->first.find(var_str+":") != std::string::npos)
                       func_arg_rd[func].push_back(std::to_string(i) + it->first.substr(it->first.find(":")));
              }
          }
          i++;
    }
    for (int i = 0; i < func_arg_rd[func].size(); i++)
         errs() << "Arg RD: " << func_arg_rd[func][i] << "\n";
    setFuncRD(func, func_arg_rd[func]);
*/
    for (std::map<Value*, std::set<std::string> >::iterator it = arg_redef.begin(); it != arg_redef.end(); it++) {
        if (!isa<Argument>(it->first))
            continue;
        int idx = dyn_cast<Argument>(it->first)->getArgNo();
        for (auto fd : arg_redef[it->first])
            errs() << "Arg RD: " << idx << ":" << fd << "\n";
    }
}

std::string getCallee(Value* v) {
    if (CallInst* CI = dyn_cast<CallInst>(v)) {
        Function* fun = CI->getCalledFunction();
        if (fun)
            return fun->getName();
    } else if (InvokeInst* CI = dyn_cast<InvokeInst>(v)) {
        Function* fun = CI->getCalledFunction();
        if (fun)
            return fun->getName();
    }
    return "";
}

void setFuncRD(std::string func, std::vector<std::string>& idx) {
    std::string file_name = func + ".df";
    std::ofstream outfile;
    outfile.open(file_name.c_str());
    if (outfile.is_open()) {
        for (int i = 0; i < idx.size(); i++)
            outfile << idx[i] << "\n";
        outfile.close();
    }
}

std::string loadFuncRD(std::string func) {
    std::string file_name = func + ".df";
    std::ifstream infile;
    std::string def_var = "";
    std::string line;
    infile.open(file_name.c_str());
    if (!infile.is_open())
        return "";
    while (!infile.eof()) {
        getline(infile, line);
        if (line.length() == 0)
            continue;
        def_var += (line + ";");
    }
    infile.close();
    if (def_var != "")
        def_var = def_var.substr(0, def_var.length() - 1);
    return def_var;
}

// arg id starting from 0
Value* getCalleeArg(Value* v, int i) {
    if (i < 0)
        return NULL;
    if (CallInst* CI = dyn_cast<CallInst>(v)) {
        Value* val = CI->getArgOperand(i);
        return val;
    } else if (InvokeInst* CI = dyn_cast<InvokeInst>(v)) {
        Value* val = CI->getArgOperand(i);
        return val;
    }
    return NULL;
}

void valueToAllDefinitionVar(Value* v, std::vector<Value*>& def_var, std::vector<std::string>& def_field) {
    if (isa<Argument>(v)) {
        def_var.push_back(v);
        def_field.push_back("");
    } else if (isa<StoreInst>(v)) {
        def_var.push_back(((StoreInst*)v)->getPointerOperand());
        def_field.push_back("");
    } else if (isa<CallInst>(v) || isa<InvokeInst>(v)) {
        // Read callee's dataflow profile to get any defined args and LHS (if any)
        std::string def_str = "";
        std::string callee_func = getCallee(v);
        if (callee_func != "") {
            std::string def_arg = loadFuncRD(callee_func);
            //errs() << "Debug: " << callee_func << "###" << def_arg << "\n";
            if (def_arg != "") {
                while (def_arg.find(";") != std::string::npos) {
                    std::string curr = def_arg.substr(0, def_arg.find(";"));
                    int idx = -1;
                    std::string field_idx = "";
                    if (curr.find(":") != std::string::npos) {
                        idx = atoi(curr.substr(0, curr.find(":")).c_str());
                        field_idx = curr.substr(curr.find(":"));
                    } else {
                        idx = atoi(curr.c_str());
                    }
                    Value* callee_arg = getCalleeArg(v, idx);
                    if (callee_arg != NULL) {
                        def_var.push_back(callee_arg);
                        def_field.push_back(field_idx);
                    }
                    def_arg = def_arg.substr(def_arg.find(";") + 1);
                }
                int idx = -1;
                std::string field_idx = "";
                if (def_arg.find(":") != std::string::npos) {
                    idx = atoi(def_arg.substr(0, def_arg.find(":")).c_str());
                    field_idx = def_arg.substr(def_arg.find(":"));
                } else {
                    idx = atoi(def_arg.c_str());
                }
                Value* callee_arg = getCalleeArg(v, idx);
                if (callee_arg != NULL) {
                    def_var.push_back(callee_arg);
                    def_field.push_back(field_idx);
                }
            }
        }
    }
    if (isa<Instruction>(v)) {
        if (!dyn_cast<Instruction>(v)->getType()->isVoidTy()) {
            def_var.push_back(v);
            def_field.push_back("");
        }
    }
}

Value* valueToDefinitionVar(Value* v) {
    if (isa<Argument>(v)) {
        return v;
    } else if (isa<StoreInst>(v)) {
        return ((StoreInst*)v)->getPointerOperand();
    } else if (isa<Instruction>(v)) {
        if (dyn_cast<Instruction>(v)->getType()->isVoidTy())
            return NULL;
        else
            return v;
    } else {
        return NULL;
    }
}

std::string setToStr(std::vector<Value*>& domain, const BitVector& includedInSet, std::string (*valFormatFunc)(Value*)) {
    std::stringstream ss;
    ss << "{\n";
    int numInSet = 0;
    for (int i = 0; i < domain.size(); i++) {
        if (includedInSet[i]) {
            if (numInSet > 0) ss << " \n";
            numInSet++;
            ss << "    " << valFormatFunc(domain[i]);
        }
    }
    ss << "}";
    return ss.str();
}

/* End string output utilities *
******************************************************************************************/

DataFlowResult DataFlow::run(Function& F,
                             std::vector<Value*>& domain,
                             Direction direction,
                             BitVector boundaryCond,
                             BitVector initInteriorCond, std::set<BasicBlock*>& prune_bb) {
    DenseMap<BasicBlock*, DataFlowResultForBlock> resultsByBlock;
    bool analysisConverged = false;

    //Create mapping from domain entries to linear indices
    //(simplifies updating bitvector entries given a particular domain element)
    DenseMap<Value*, int> domainEntryToValueIdx;
    for (int i = 0; i < domain.size(); i++)
        domainEntryToValueIdx[domain[i]] = i;

    //Set initial val for boundary blocks, which depend on direction of analysis
    std::set<BasicBlock*> boundaryBlocks;
    switch (direction) {
        case FORWARD:
            boundaryBlocks.insert(&F.front());  //post-"entry" block = first in list
            break;
        case BACKWARD:
            //Pre-"exit" blocks = those that have a return statement
            for (Function::iterator I = F.begin(), E = F.end(); I != E; ++I)
                if (isa<ReturnInst>(I->getTerminator()))
                    boundaryBlocks.insert(&*I);
            break;
    }
    for (std::set<BasicBlock*>::iterator boundaryBlock = boundaryBlocks.begin(); boundaryBlock != boundaryBlocks.end(); boundaryBlock++) {
        DataFlowResultForBlock boundaryResult = DataFlowResultForBlock();
        //Set either the "IN" of post-entry blocks or the "OUT" of pre-exit blocks (since entry/exit blocks don't actually exist...)
        BitVector* boundaryVal = (direction == FORWARD) ? &boundaryResult.in : &boundaryResult.out;
        *boundaryVal = boundaryCond;
        boundaryResult.currTransferResult.baseValue = boundaryCond;
        resultsByBlock[*boundaryBlock] = boundaryResult;
    }

    //Set initial vals for interior blocks (either OUTs for fwd analysis or INs for bwd analysis)
    for (Function::iterator basicBlock = F.begin(); basicBlock != F.end(); ++basicBlock) {
        if (prune_bb.find(&*basicBlock) != prune_bb.end()) continue;
        if (boundaryBlocks.find(&*basicBlock) == boundaryBlocks.end()) {
            DataFlowResultForBlock interiorInitResult = DataFlowResultForBlock();
            BitVector* interiorInitVal = (direction == FORWARD) ? &interiorInitResult.out : &interiorInitResult.in;
            *interiorInitVal = initInteriorCond;
            interiorInitResult.currTransferResult.baseValue = initInteriorCond;
            resultsByBlock[&*basicBlock] = interiorInitResult;
        }
    }

    //Generate analysis "predecessor" list for each block (depending on direction of analysis)
    //Will be used to drive the meet inputs.
    DenseMap<BasicBlock*, std::vector<BasicBlock*> > analysisPredsByBlock;
    for (Function::iterator basicBlock = F.begin(); basicBlock != F.end(); ++basicBlock) {
        if (prune_bb.find(&*basicBlock) != prune_bb.end()) continue;
        std::vector<BasicBlock*> analysisPreds;
        switch (direction) {
            case FORWARD:
                for (pred_iterator predBlock = pred_begin(&*basicBlock), E = pred_end(&*basicBlock); predBlock != E; ++predBlock)
                    analysisPreds.push_back(*predBlock);
                break;
            case BACKWARD:
                for (succ_iterator succBlock = succ_begin(&*basicBlock), E = succ_end(&*basicBlock); succBlock != E; ++succBlock)
                    analysisPreds.push_back(*succBlock);
                break;
        }

        analysisPredsByBlock[&*basicBlock] = analysisPreds;
    }

    //Iterate over blocks in function until convergence of output sets for all blocks
    while (!analysisConverged) {
        analysisConverged = true;  //assume converged until proven otherwise during this iteration

        //TODO: if analysis is backwards, may want instead to iterate from back-to-front of blocks list
        // errs() << "run " << F.getName() << "\n";
        for (Function::iterator basicBlock = F.begin(); basicBlock != F.end(); ++basicBlock) {
            if (prune_bb.find(&*basicBlock) != prune_bb.end()) continue;
            DataFlowResultForBlock& blockVals = resultsByBlock[&*basicBlock];

            //Store old output before applying this analysis pass to the block (depends on analysis dir)
            DataFlowResultForBlock oldBlockVals = blockVals;
            BitVector oldPassOut = (direction == FORWARD) ? blockVals.out : blockVals.in;

            //If any analysis predecessors have outputs ready, apply meet operator to generate updated input set for this block
            BitVector* passInPtr = (direction == FORWARD) ? &blockVals.in : &blockVals.out;
            std::vector<BasicBlock*> analysisPreds = analysisPredsByBlock[&*basicBlock];
            std::vector<BitVector> meetInputs;
            //Iterate over analysis predecessors in order to generate meet inputs for this block
            // errs() << "run BB " << (*basicBlock).getName() << "\n";
            for (std::vector<BasicBlock*>::iterator analysisPred = analysisPreds.begin(); analysisPred < analysisPreds.end(); ++analysisPred) {
                if (prune_bb.find(*analysisPred) != prune_bb.end()) continue;
                DataFlowResultForBlock& predVals = resultsByBlock[*analysisPred];

                BitVector meetInput = predVals.currTransferResult.baseValue;

                //If this pred matches a predecessor-specific value for the current block, union that value into value set
                DenseMap<BasicBlock*, BitVector>::iterator predSpecificValueEntry = predVals.currTransferResult.predSpecificValues.find(&*basicBlock);
                if (predSpecificValueEntry != predVals.currTransferResult.predSpecificValues.end()) {
                    //            errs() << "Pred-specific meet input from " << (*analysisPred)->getName() << ": " <<bitVectorToStr(predSpecificValueEntry->second) << "\n";
                    meetInput |= predSpecificValueEntry->second;
                }

                meetInputs.push_back(meetInput);
            }
            //      errs() << "run BB " << (*basicBlock).getName() << " meet" << "\n";
            if (!meetInputs.empty())
                *passInPtr = applyMeet(meetInputs);

            //      errs() << "run BB " << (*basicBlock).getName() << " " << domainEntryToValueIdx.size() << " transfer" << "\n";
            //Apply transfer function to input set in order to get output set for this iteration
            blockVals.currTransferResult = applyTransfer(*passInPtr, domainEntryToValueIdx, &*basicBlock);
            BitVector* passOutPtr = (direction == FORWARD) ? &blockVals.out : &blockVals.in;
            *passOutPtr = blockVals.currTransferResult.baseValue;

            //      errs() << "run BB " << " done" << "\n"; //(*basicBlock).getName() << " done" << "\n";
            //Update convergence: if the output set for this block has changed, then we've not converged for this iteration
            if (analysisConverged) {
                if (*passOutPtr != oldPassOut)
                    analysisConverged = false;
                else if (blockVals.currTransferResult.predSpecificValues.size() != oldBlockVals.currTransferResult.predSpecificValues.size())
                    analysisConverged = false;
                //(should really check whether contents of pred-specific values changed as well, but
                // that doesn't happen when the pred-specific values are just a result of phi-nodes)
            }
        }
    }

    DataFlowResult result;
    result.domainEntryToValueIdx = domainEntryToValueIdx;
    result.resultsByBlock = resultsByBlock;
    return result;
}

void DataFlow::PrintInstructionOps(raw_ostream& O, const Instruction* I) {
    O << "\nOps: {";
    if (I != NULL) {
        for (Instruction::const_op_iterator OI = I->op_begin(), OE = I->op_end();
             OI != OE; ++OI) {
            const Value* v = OI->get();
            v->print(O);
            O << ";";
        }
    }
    O << "}\n";
}

void DataFlow::ExampleFunctionPrinter(raw_ostream& O, const Function& F) {
    for (Function::const_iterator FI = F.begin(), FE = F.end(); FI != FE; ++FI) {
        const BasicBlock* block = &*FI;
        O << block->getName() << ":\n";
        const Value* blockValue = block;
        PrintInstructionOps(O, NULL);
        for (BasicBlock::const_iterator BI = block->begin(), BE = block->end();
             BI != BE; ++BI) {
            BI->print(O);
            PrintInstructionOps(O, &(*BI));
        }
    }
}

}  // namespace llvm
