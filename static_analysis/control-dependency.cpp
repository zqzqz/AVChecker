#include "control-dependency.h"
#include <stack>

namespace llvm {

char ControlDependency::ID = 1;
static RegisterPass<ControlDependency> A("control-dependency", "control dependency analysis on given function", false, true);

bool ControlDependency::doInitialization(Module &M) {
    //record the source function name
    std::ifstream configFile("config.tmp");
    std::string configPath = "";
    if (configFile.is_open()) {
        std::getline(configFile, configPath);
    }

    std::ifstream sourceFile(configPath + "/source.meta");
    if (sourceFile.is_open()) {
        std::string func;
        while (std::getline(sourceFile, func))
            TargetSources.insert(func);
        sourceFile.close();
    }

    //record the sink function name
    std::ifstream sinkfile(configPath + "/sink.meta");
    if (sinkfile.is_open()) {
        std::string func;
        while (std::getline(sinkfile, func))
            TargetSinks.insert(func);
        sinkfile.close();
    }

    std::ifstream myFile(configPath + "/func.meta");
    if (myFile.is_open()) {
        std::string func;
        while (std::getline(myFile, func))
            TargetFuncs.insert(func);
        myFile.close();
    }

    for (Function &F : M) {
        std::string funcName = demangle(F.getName().str().c_str());
        if (TargetFuncs.find(funcName) != TargetFuncs.end()) {
            TargetFuncPtrs.insert(&F);
        }
        if (TargetSinks.find(funcName) != TargetSinks.end()) {
            TargetSinkPtrs.insert(&F);
        }
        if (TargetSources.find(funcName) != TargetSources.end()) {
            TargetSourcePtrs.insert(&F);
        }
    }

    initAlias(M);
    initVectorDeps(M);

    return false;
}

bool ControlDependency::doFinalization(Module &M) {
    return false;
}

bool ControlDependency::runOnModule(Module &M) {
    // for (Function &F : M) {
    //     errs() << demangle(F.getName().str().c_str()) << "\n";
    // }

    CallGraph &CG = getAnalysis<CallGraphWrapperPass>().getCallGraph();
    buildCallGraph(&M, &CG);
    errs() << "Number of functions ready for CD analysis: " << FunctionData.size() << "\n";
    for (Function &F : M) {
        runOnFunction(F);
    }
    errs() << "Eval Instr " << instr_cnt << " / " << instr_total << "\n";
    errs() << "Eval BB " << bb_cnt << " / " << bb_total << "\n";
    return false;
}

bool ControlDependency::runOnFunction(Function &F) {
    std::string funcName = demangle(F.getName().str().c_str());

    // F is a function declaration without function body
    if (F.isDeclaration())
        return false;

    // F is out of our analysis scope
    if (FunctionData.find(&F) == FunctionData.end())
        return false;

    errs() << "Start control-dependency on " << funcName << "\n";

    // init MCFG
    MCFG[&F] = std::vector<MNode *>();

    // Loop Headers
    std::set<BasicBlock *> loopHeaders;
    LoopInfo &LI = getAnalysis<LoopInfoWrapperPass>(F).getLoopInfo();

    // CDs
    std::map<BasicBlock *, std::vector<CDNode>> CDMap;
    PostDominatorTree &PDT = getAnalysis<PostDominatorTreeWrapperPass>(F).getPostDomTree();

    // control dependency analysis
    for (Function::iterator b = F.begin(); b != F.end(); b++) {
        BasicBlock *A = &(*b);
        for (succ_iterator succ = succ_begin(A), end = succ_end(A); succ != end; ++succ) {
            BasicBlock *B = *succ;
            if (!(A && B))
                continue;
            if (A == B || !PDT.dominates(B, A)) {
                BasicBlock *lub = PDT[A]->getIDom()->getBlock();
                BasicBlock *tmp = B;
                while (tmp != lub) {
                    CDNode curNode(A, B, getEdgeType(A, B));
                    CDMap[tmp].push_back(curNode);
                    tmp = PDT[tmp]->getIDom()->getBlock();
                }
            }
        }
        if (LI.isLoopHeader(A)) {
            loopHeaders.insert(A);
        }
    }
    // select minimal required CDNodes
    std::stack<BasicBlock *> stackBB;
    std::stack<std::pair<Instruction *, Value *>> stackVal;
    std::set<BasicBlock *> finishedBB;
    std::set<std::pair<Instruction *, Value *>> finishedVal;
    std::set<BasicBlock *> CDFrom;
    std::set<BasicBlock *> CDTo;
    // put vector::push_back / emplace_back into the stack
    for (Instruction *I : VectorDeps[&F]) {
        stackBB.push(I->getParent());
        MNode *mnode = new MNode(I->getParent());
        mnode->addInstr(I);
        MCFG[&F].push_back(mnode);
    }
    // put sinkBBs in the stack
    for (SinkBBNode *sinkBB : FunctionData[&F]) {
        stackBB.push(sinkBB->BB);
        MNode *mnode = new MNode(sinkBB->BB);
        mnode->addInstr(sinkBB->I);
        MCFG[&F].push_back(mnode);
    }
    // start analysis
    while (!stackBB.empty()) {
        BasicBlock *BB = stackBB.top();
        stackBB.pop();
        if (finishedBB.find(BB) != finishedBB.end()) {
            continue;
        }
        
        // add sink Instruction to value analysis
        SinkBBNode *snode = getSinkBBNode(&F, BB);
        if (snode) {
            Instruction *I = snode->I;
            for (auto op = I->op_begin(); op != I->op_end(); op++) {
                auto val = std::make_pair(I, dyn_cast<Value>(*op));
                if (finishedVal.find(val) == finishedVal.end()) {
                    stackVal.push(val);
                }
            }
        }

        // add vector push_back Instruction to value analysis
        if (VectorDeps[&F].find(BB->getTerminator()) != VectorDeps[&F].end()) {
            Instruction *I = BB->getTerminator();
            for (auto op = I->op_begin(); op != I->op_end(); op++) {
                if (!isa<Instruction>(*op)) continue;  
                auto val = std::make_pair(I, dyn_cast<Value>(*op));
                if (finishedVal.find(val) == finishedVal.end()) {
                    stackVal.push(val);
                }
            }
        }

        // push CDs into stack if any CD is not been analyzed before
        // errs() << "CD of " << BB->getName() << ":";
        // for (CDNode cnode : CDMap[BB]) {
        //     errs() << " " << cnode.from->getName();
        // }
        // errs() << "\n";
        for (CDNode cnode : CDMap[BB]) {
            // update MCFG
            MNode *mnode = getMNode(&F, cnode.from);
            if (!mnode) {
                mnode = new MNode(cnode.from);
                MCFG[&F].push_back(mnode);
            }

            // update edges
            mnode->addEdges(cnode.E);
            CDFrom.insert(cnode.from);
            CDTo.insert(cnode.to);
            stackBB.push(cnode.from);

            // extract branch operands
            Instruction *I = mnode->BB->getTerminator();
            // do not add branch instruction to instrs list
            // mnode->addInstr(I);
            if (isa<CallBase>(I)) continue;
            for (auto op = I->op_begin(); op != I->op_end(); op++) {
                if (!isa<Instruction>(*op)) continue;
                auto val = std::make_pair(I, dyn_cast<Value>(*op));
                if (finishedVal.find(val) == finishedVal.end()) {
                    stackVal.push(val);
                }
            }
        }
        // trace variable values
        while (!stackVal.empty()) {
            auto val = stackVal.top();
            stackVal.pop();
            std::set<Instruction *> defs = getDefinitions(&F, val.first, val.second);
            for (Instruction *def : defs) {
                BasicBlock *defParent = def->getParent();
                // update stack
                // if (finishedBB.find(defParent) == finishedBB.end()) {
                // update MCFG
                MNode *mnode = getMNode(&F, defParent);
                if (!mnode) {
                    mnode = new MNode(defParent);
                    MCFG[&F].push_back(mnode);
                }
                mnode->addInstr(def);
                mnode->addDU(def, val.first, val.second);
                MNode *useNode = getMNode(&F, val.first->getParent());
                if (useNode) {
                    useNode->addUD(val.first, val.second, def);
                }
                // require further CD analysis
                stackBB.push(defParent);
                for (auto op = def->op_begin(); op != def->op_end(); op++) {
                    // if(!isa<Instruction>(op) continue;
                    auto new_val = std::make_pair(def, dyn_cast<Value>(*op));
                    if (finishedVal.find(new_val) == finishedVal.end()) {
                        stackVal.push(new_val);
                    }
                }
            }

            // processing a value finished
            if (finishedVal.find(val) == finishedVal.end()) {
                // errs() << "processed value " << val->getName() << "\n";
                finishedVal.insert(val);
            }
        }
        // processing a BB finished
        if (finishedBB.find(BB) == finishedBB.end()) {
            // errs() << "processed BB " << BB->getName() << "\n";
            finishedBB.insert(BB);
        }
    }

    // remove abundant edge restrictions
    for (BasicBlock *from : CDFrom) {
        for (BasicBlock *to : CDTo) {
            if (PDT.dominates(from, to)) {
                MNode *mnode = getMNode(&F, from);
                if (mnode) {
                    mnode->edges.clear();
                }
                break;
            }
        }
    }

    int instrs = 0;
    for (MNode *BB : MCFG[&F]) {
        instrs += BB->instrs.size();
    }
    int total_instrs = 0;
    for (BasicBlock &BB : F) {
        total_instrs += BB.size();
    }

    // errs() << "Finish control-dependency on " << funcName << " with " << instrs << "/" << total_instrs << " selected Instrs\n";
    // errs() << "Finish control-dependency on " << funcName << " with " << MCFG[&F].size() << "/" << F.getBasicBlockList().size() << " selected BBs\n";
    instr_cnt += instrs;
    instr_total += total_instrs;
    bb_cnt += MCFG[&F].size();
    bb_total += F.getBasicBlockList().size();
    
    return false;
}

void ControlDependency::initAlias(Module &M) {
    for (Function &F : M) {
        if (TargetFuncPtrs.find(&F) == TargetFuncPtrs.end()) {
            continue;
        }
        for (BasicBlock &BB : F) {
            for (Instruction &I : BB) {
                if (I.getOpcode() == Instruction::GetElementPtr) {
                    Value *op = I.getOperand(0);
                    Alias[op].insert(&I);
                }
                if (I.getOpcode() == Instruction::Store) {
                    Alias[I.getOperand(1)] = Alias[I.getOperand(0)];
                } 
            }
        }
    }
}

void ControlDependency::initVectorDeps(Module &M) {
    std::set<Value*> finishedDeps;
    for (Function *F : TargetFuncPtrs) {
        finishedDeps.clear();
        VectorDeps[F] = std::set<Instruction *>();
        for (BasicBlock &BB : *F) {
            for (Instruction &I : BB) {
                if (isa<CallBase>(I)) {
                    CallBase *II = dyn_cast<CallBase>(&I);
                    if (II->getCalledFunction() == nullptr) {
                        continue;
                    }
                    std::string calledFuncName = II->getCalledFunction()->getName();
                    if (calledFuncName.find("push_back") != std::string::npos || calledFuncName.find("emplace_back") != std::string::npos) {
                        if (II->arg_size() == 0) continue;
                        Instruction *vec = dyn_cast<Instruction>(&(II->getArgOperandUse(0)));
                        if (isVectorType(vec)) {
                            VectorDeps[F].insert(&I);
                            VectorSources[F].insert(std::make_pair(vec, false));
                            finishedDeps.insert(vec);
                        }
                    }
                }
            }
        }

        BasicBlock &entry = F->getEntryBlock();
        for (Instruction &I : entry) {
            if (I.getOpcode() == Instruction::Alloca && finishedDeps.find(&I) == finishedDeps.end() && isVectorType(&I)) {
                std::string varName = I.getName();
                if (varName.find("finished") != std::string::npos) {
                    VectorSources[F].insert(std::make_pair(&I, false));
                } else {
                    VectorSources[F].insert(std::make_pair(&I, true));
                }
            }
        }

        std::set<std::pair<Value*, bool>> extraSources;
        extraSources.clear();
        for (BasicBlock &BB : *F) {
            for (Instruction &I : BB) {
                if (I.getOpcode() == Instruction::Store) {
                    Value *vec = dyn_cast<Value>(I.getOperand(1));
                    if (!isVectorType(vec)) continue;
                    for (auto s : VectorSources[F]) {
                        if (s.first == vec) {
                            if (!isa<Instruction>(I.getOperand(0))) continue;
                            Value *vec2 = dyn_cast<Instruction>(I.getOperand(0));
                            if (finishedDeps.find(vec2) != finishedDeps.end()) continue;
                            extraSources.insert(std::make_pair(vec2, s.second));
                        }
                    }
                }
            }
        }

        for (auto s : extraSources) {
            VectorSources[F].insert(s);
        }
    }
}

// find sink BB from FunctionData map. If error or not found, return nullptr
SinkBBNode *ControlDependency::getSinkBBNode(Function *F, BasicBlock *BB) {
    if (FunctionData.find(F) == FunctionData.end()) {
        return nullptr;
    }
    for (SinkBBNode *node : FunctionData[F]) {
        if (node->BB == BB) {
            return node;
        }
    }
    return nullptr;
}

// find MNode from MCFG map; If not found, try to initialize one
MNode *ControlDependency::getMNode(Function *F, BasicBlock *BB) {
    if (MCFG.find(F) == MCFG.end()) {
        return nullptr;
    }
    for (MNode *node : MCFG[F]) {
        if (node->BB == BB) {
            return node;
        }
    }
    return nullptr;
}

std::set<Instruction *> ControlDependency::getDefinitions(Function *F, Instruction *I, Value *val) {
    std::set<Instruction *> results;
    // need reaching-definitions here
    ReachingDefinitions &RD = getAnalysis<ReachingDefinitions>();

    std::string funcName = demangle(F->getName().str().c_str());
    if (RD.func_reaching_def.find(funcName) == RD.func_reaching_def.end() ||
        RD.func_instr_bb_map.find(funcName) == RD.func_instr_bb_map.end() ||
        RD.func_reaching_def[funcName].find(I) == RD.func_reaching_def[funcName].end()) {
        if (isa<Instruction>(val) && results.size() == 0) {
            results.insert(dyn_cast<Instruction>(val));
        }
        return results;
    }

    std::set<Value *> vals = Alias[val];
    vals.insert(val);

    for (Value *oneVal : vals) {
        for (Value *def : RD.func_reaching_def[funcName][I]) {
            if (!def) {
                continue;
            }
            if (def == I) {
                continue;
            }

            Value *defVar = valueToDefVar(def);
            if (oneVal == defVar) {
                if (isa<Instruction>(def)) {
                    Instruction *defI = dyn_cast<Instruction>(def);
                    if (results.find(defI) == results.end()) {
                        if (isa<StoreInst>(defI) && isa<Instruction>(defI->getOperand(0))) {
                            results.insert(dyn_cast<Instruction>(defI->getOperand(0)));
                        } else {
                            results.insert(defI);
                        }
                    }
                }
            }
        }
    }
    if (isa<Instruction>(val) && results.size() == 0) {
        results.insert(dyn_cast<Instruction>(val));
    }
    return results;
}

EdgeType ControlDependency::getEdgeType(const BasicBlock *A, const BasicBlock *B) {
    if (const BranchInst *i = dyn_cast<BranchInst>(A->getTerminator())) {
        if (i->isConditional()) {
            if (i->getSuccessor(0) == B) {
                return EdgeType::TRUE;
            } else if (i->getSuccessor(1) == B) {
                return EdgeType::FALSE;
            } else {
                assert(false && "Asking for edge type between unconnected basic blocks!");
            }
        }
    } else if (const InvokeInst *i = dyn_cast<InvokeInst>(A->getTerminator())) {
        if (i->getNormalDest() == B) {
            return EdgeType::INVOKE_TRUE;
        } else if (i->getUnwindDest() == B) {
            return EdgeType::INVOKE_FALSE;
        } else {
            assert(false && "Asking for edge type between unconnected basic blocks!");
        }
    }
    return EdgeType::UNKNOWN;
}

void ControlDependency::buildCallGraph(Module *M, CallGraph *CG) {
    std::set<Function *> sinkCallee = TargetSinkPtrs;
    // init CallChains
    for (Function *sink : sinkCallee) {
        std::vector<Function *> v;
        v.push_back(sink);
        CallChains.push_back(v);
    }
    bool changed = true;
    while (changed) {
        changed = false;
        for (Function *F : TargetFuncPtrs) {
            CallGraphNode *N = (*CG)[F];
            for (auto callRecord : *N) {
                if (callRecord.first == nullptr) {
                    // something wrong
                    continue;
                }
                Function *calledFunc = callRecord.second->getFunction();
                if (calledFunc == nullptr) {
                    if (isa<CallBase>(callRecord.first)) {
                        calledFunc = getCalledFunction(dyn_cast<CallBase>(callRecord.first));
                    }
                }
                if (calledFunc == nullptr) {
                    continue;
                }
                if (TargetFuncPtrs.find(calledFunc) == TargetFuncPtrs.end() && TargetSinkPtrs.find(calledFunc) == TargetSinkPtrs.end()) {
                    continue;
                }
                Instruction *I = nullptr;
                if (isa<CallInst>(callRecord.first)) {
                    I = dyn_cast<CallInst>(callRecord.first);
                } else if (isa<InvokeInst>(callRecord.first)) {
                    I = dyn_cast<InvokeInst>(callRecord.first);
                } else {
                    // unrecognized instruction type
                    continue;
                }

                BasicBlock *BB = I->getParent();
                // add sink block node
                if (!getSinkBBNode(F, BB)) {
                    changed = true;
                    FunctionData[F].push_back(new SinkBBNode(BB, I, F, calledFunc));
#ifdef DEBUG
                    errs() << demangle(F->getName().str().c_str()) << " call " << demangle(calledFunc->getName().str().c_str()) << "\n";
#endif              
                }
                
                if (sinkCallee.find(calledFunc) != sinkCallee.end()) {
                    sinkCallee.insert(F);

                    // update CallChains
                    std::vector<std::vector<Function *>> selectedChains;
                    for (auto chain : CallChains) {
                        if (chain.back() == calledFunc) {
                            selectedChains.push_back(chain);
                        }
                    }
                    for (auto chain : selectedChains) {
                        chain.push_back(F);
                        if (std::find(CallChains.begin(), CallChains.end(), chain) == CallChains.end()) {
                            changed = true;
                            CallChains.push_back(chain);
                        }
                    }
                }
            }
        }
    }

    // clean chains
    auto it = CallChains.begin();
    while (it != CallChains.end()) {
        std::string funcName = demangle(it->back()->getName().str().c_str());
        if (TargetSources.find(funcName) == TargetSources.end()) {
            it = CallChains.erase(it);
        } else {
            it++;
        }
    }

    // deal with internal calls
    for (Function *F : TargetFuncPtrs) {
        if (sinkCallee.find(F) == sinkCallee.end()) {
#ifdef DEBUG
            errs() << "inter call " << demangle(F->getName().str().c_str()) << "\n";
#endif
            // it is an internal call
            for (auto it = FunctionData.begin(); it != FunctionData.end(); it++) {
                auto sinkBB = it->second.begin();
                while (sinkBB != it->second.end()) {
                    if ((*sinkBB)->to == F) {
                        InterCalls[(*sinkBB)->I] = F;
                        sinkBB = it->second.erase(sinkBB);
                    } else {
                        sinkBB++;
                    }
                }
            }
            // set return instruction as the sinks
            for (BasicBlock &BB: *F) {
                for (Instruction &I : BB) {
                    if (I.getOpcode() == Instruction::Ret) {
                        FunctionData[F].push_back(new SinkBBNode(&BB, &I, F, nullptr));
                    }
                }
            }
        }
    }
}

}  // namespace llvm
