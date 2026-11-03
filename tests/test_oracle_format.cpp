// SPDX-License-Identifier: GPL-3.0-only
#include "../plugin/OracleFormat.h"
#include "../plugin/OracleSpeedControl.h"
#include <iostream>
#include <limits>
#include <set>
#include <sstream>
#include <io.h>
#include <fcntl.h>
static unsigned int checks=0;
static void require(bool okay){++checks;if(!okay)throw std::runtime_error("oracle format assertion failed");}
// State 0.5 goal: fake objects with the member names and shapes that
// goalFromAI and goalFromTaskSystem read (AI, AITaskSytem, TaskMatch, TaskData).
struct FakeHand {unsigned int serial;};
struct FakeTaskData {int key;};
struct FakeTaskMatch {const FakeTaskData* taskData;FakeHand subject;};
struct FakeTaskSystem {FakeTaskMatch currentGoal;int currentGoalPriority;};
struct FakeAI {FakeTaskSystem* taskSystemAI;};
static const char* fakeRowName(int row){
    switch(row){case 4:return "melee_attack";case 14:return "idle";case 37:return "wander_town";case 180:return "man_the_gate";case 290:return "bash_gate_player_order";case 200:return 0;case 201:return "";default:return "other_row";}
}
static std::string fakeHandId(const FakeHand& hand){
    if(!hand.serial)return std::string();std::ostringstream s;s<<"hand:1:7:101:2:"<<hand.serial;return s.str();
}
static json::Value fakeGoal(const FakeAI* ai){return oracle::goalFromAI(ai,fakeRowName,fakeHandId);}
static void goalChecks(){
    // Unknown objects give null: no AI, no task system, no taskData.
    require(fakeGoal(0).type==json::Value::NIL);
    FakeAI ai={0};require(fakeGoal(&ai).type==json::Value::NIL);
    FakeTaskSystem tasks={{0,{0}},1};ai.taskSystemAI=&tasks;require(fakeGoal(&ai).type==json::Value::NIL);
    require(oracle::goalFromTaskSystem((const FakeTaskSystem*)0,fakeRowName,fakeHandId).type==json::Value::NIL);
    // A Task_Blank row (wander_town, 37) is a goal and keeps its name.
    FakeTaskData data={37};tasks.currentGoal.taskData=&data;
    require(oracle::canonical(fakeGoal(&ai))=="{\"priority\":\"fluff\",\"target_id\":null,\"type\":\"wander_town\"}\n");
    // NULL_TASK, rows outside 0 to 290 and rows without a name give null.
    {const int outside[]={0,-1,291,292,1000,0x7fffffff,(int)0x80000000,200,201};
     for(int i=0;i<9;++i){data.key=outside[i];require(fakeGoal(&ai).type==json::Value::NIL&&oracle::canonical(fakeGoal(&ai))=="null\n");}}
    require(oracle::goalNullTaskRow==0&&oracle::goalLastTaskRow==290);
    data.key=290;require(fakeGoal(&ai).at("type").str=="bash_gate_player_order");
    data.key=1;require(fakeGoal(&ai).at("type").str=="other_row");
    // Every taskPriority tier by name; any other raw value is a null priority
    // and the type and target are kept.
    {const char* names[]={"just_action","fluff","non_urgent","urgent","obedience"};data.key=14;
     for(int i=0;i<5;++i){tasks.currentGoalPriority=i;require(fakeGoal(&ai).at("priority").str==names[i]&&oracle::canonical(oracle::goalPriorityName(i))=="\""+std::string(names[i])+"\"\n");}}
    {const int outside[]={-1,5,6,255,0x7fffffff,(int)0x80000000};tasks.currentGoal.subject.serial=1002;
     for(int i=0;i<6;++i){tasks.currentGoalPriority=outside[i];const json::Value goal=fakeGoal(&ai);require(oracle::goalPriorityName(outside[i]).type==json::Value::NIL);
      require(goal.type==json::Value::OBJECT&&goal.object.size()==3&&goal.at("priority").type==json::Value::NIL&&goal.at("type").str=="idle"&&goal.at("target_id").str=="hand:1:7:101:2:1002");}}
    // A subject hand is encoded by the hand-id function, as order.target_id; an empty id is null.
    data.key=4;tasks.currentGoalPriority=3;tasks.currentGoal.subject.serial=1002;
    require(oracle::canonical(fakeGoal(&ai))=="{\"priority\":\"urgent\",\"target_id\":\"hand:1:7:101:2:1002\",\"type\":\"melee_attack\"}\n");
    tasks.currentGoal.subject.serial=0;require(fakeGoal(&ai).at("target_id").type==json::Value::NIL);
    // The task system path alone gives the same value as through the AI.
    require(oracle::canonical(oracle::goalFromTaskSystem(&tasks,fakeRowName,fakeHandId))==oracle::canonical(fakeGoal(&ai)));
}
static void badFilename(const char* name){bool failed=false;try{oracle::validateFilename(name);}catch(const oracle::Error& e){failed=e.code=="invalid_request";}require(failed);}
int main(int argc,char** argv){try{
    if(argc==2&&std::string(argv[1])=="--canonical"){
        _setmode(_fileno(stdout),_O_BINARY);
        std::string input;while(std::getline(std::cin,input))std::cout<<oracle::canonical(json::Parser(input).parse());return 0;
    }
    require(_MSC_VER==1600&&sizeof(void*)==8);
    int firstWorld=0,secondWorld=0;oracle::SpeedSelection selection;
    require(!selection.known);selection.remember(1,"probe_command");require(!selection.known);
    selection.synchronize(&firstWorld,true);require(!selection.known);
    selection.remember(5,"probe_command");require(selection.known&&selection.speed==5);
    selection.remember(0,"observed_running");require(selection.known&&selection.speed==5&&std::string(selection.source)=="probe_command");
    selection.synchronize(&firstWorld,true);require(selection.known&&selection.speed==5);
    selection.synchronize(&firstWorld,false);require(!selection.known);
    selection.synchronize(&firstWorld,true);require(!selection.known);
    selection.remember(2,"observed_running");require(selection.known&&selection.speed==2);
    selection.synchronize(&secondWorld,true);require(!selection.known);
    selection.remember(-1,"probe_command");selection.remember(6,"probe_command");selection.remember(std::numeric_limits<double>::quiet_NaN(),"probe_command");require(!selection.known);
    selection.remember(1,"probe_command");selection.clear();require(!selection.known&&selection.world==0);
    require(oracle::canonical(json::Value(-0.0))=="0\n");
    require(oracle::canonical(json::Value(.0000005))=="0.000001\n");
    require(oracle::canonical(json::Value(-.0000005))=="-0.000001\n");
    require(oracle::canonical(json::Value(.00000049))=="0\n");
    require(oracle::canonical(json::Value(-.00000049))=="0\n");
    require(oracle::canonical(json::Value(1.230000))=="1.23\n");
    require(oracle::canonical(json::Value(999999999.999999))=="999999999.999999\n");
    require(oracle::canonical(json::Value(1000000000.0))=="1000000000\n");
    require(oracle::canonical(json::Value(-1000000000.0))=="-1000000000\n");
    // State 0.3 slave_state: the four SlaveStateEnum names; any other raw value is null, never not_slave.
    require(oracle::canonical(oracle::slaveStateName(0))=="\"not_slave\"\n");
    require(oracle::canonical(oracle::slaveStateName(1))=="\"slave\"\n");
    require(oracle::canonical(oracle::slaveStateName(2))=="\"escaping_slave\"\n");
    require(oracle::canonical(oracle::slaveStateName(3))=="\"ex_slave\"\n");
    {const int outside[]={-1,4,5,255,0x7fffffff,(int)0x80000000};for(int i=0;i<6;++i)require(oracle::slaveStateName(outside[i]).type==json::Value::NIL&&oracle::canonical(oracle::slaveStateName(outside[i]))=="null\n");}
    // State 0.4 in_something: the three UseStuffState names; any other raw value is null, never nothing.
    require(oracle::canonical(oracle::inSomethingName(0))=="\"nothing\"\n");
    require(oracle::canonical(oracle::inSomethingName(1))=="\"bed\"\n");
    require(oracle::canonical(oracle::inSomethingName(2))=="\"prison\"\n");
    {const int outside[]={-1,3,4,255,0x7fffffff,(int)0x80000000};for(int i=0;i<6;++i)require(oracle::inSomethingName(outside[i]).type==json::Value::NIL&&oracle::canonical(oracle::inSomethingName(outside[i]))=="null\n");}
    // State 0.4 carrying: not carrying is nothing whatever the hand; a null hand while carrying is null.
    for(int hand=0;hand<4;++hand)require(oracle::canonical(oracle::carryingName(false,(hand&1)!=0,(hand&2)!=0))=="\"nothing\"\n");
    require(oracle::carryingName(true,true,false).type==json::Value::NIL&&oracle::carryingName(true,true,true).type==json::Value::NIL);
    require(oracle::canonical(oracle::carryingName(true,false,true))=="\"character\"\n");
    require(oracle::canonical(oracle::carryingName(true,false,false))=="\"other\"\n");
    // State 0.4 stats: exactly 34 distinct keys in StatsEnumerated order.
    {const char* expected[]={"strength","melee_attack","labouring","science","engineering","robotics","smithing_weapon","smithing_armour","medic","thieving","turrets","farming","cooking","stealth","athletics","dexterity","melee_defence","toughness","assassination","swimming","perception","katanas","sabres","hackers","heavyweapons","blunt","martialarts","masscombat","dodge","polearms","crossbows","friendly_fire","lockpicking","smithing_bow"};
     require(oracle::statKeyCount==34&&sizeof(expected)/sizeof(expected[0])==34&&sizeof(oracle::statKeys)/sizeof(oracle::statKeys[0])==34);std::set<std::string> distinct;
     for(size_t i=0;i<34;++i){require(std::string(oracle::statKeys[i])==expected[i]);distinct.insert(oracle::statKeys[i]);}require(distinct.size()==34);
     const char* excluded[]={"hivemedic","vet","weapons","survival","none","end"};for(int i=0;i<6;++i)require(!distinct.count(excluded[i]));}
    goalChecks();
    require(oracle::canonical(json::Parser("{\"z\":-0.0,\"a\":[true,null,\"line\\n\\u00e9\",1.1234567]}").parse())=="{\"a\":[true,null,\"line\\n\xc3\xa9\",1.123457],\"z\":0}\n");
    const double invalid[]={1000000000.1,std::numeric_limits<double>::infinity(),std::numeric_limits<double>::quiet_NaN()};
    for(int i=0;i<3;++i){bool failed=false;try{oracle::canonical(json::Value(invalid[i]));}catch(const oracle::Error& e){failed=e.code=="state_unavailable";}require(failed);}
    oracle::validateFilename("checkpoint_001-abc.json");
    const char* invalidNames[]={"../state.json","a/b.json","a\\b.json","a.json:stream","NUL.json","COM1.json","LPT9.json",".json","a.JSON","a.json.","a\n.json","x y.json"};
    for(int i=0;i<12;++i)badFilename(invalidNames[i]);
    std::cout<<"{\"passed\":true,\"checks\":"<<checks<<",\"toolset\":\"v100 x64\"}\n";return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}}
