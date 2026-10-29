// SPDX-License-Identifier: GPL-3.0-only
#include "../plugin/OracleFormat.h"
#include "../plugin/OracleSpeedControl.h"
#include <iostream>
#include <limits>
#include <io.h>
#include <fcntl.h>
static unsigned int checks=0;
static void require(bool okay){++checks;if(!okay)throw std::runtime_error("oracle format assertion failed");}
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
    require(oracle::canonical(json::Parser("{\"z\":-0.0,\"a\":[true,null,\"line\\n\\u00e9\",1.1234567]}").parse())=="{\"a\":[true,null,\"line\\n\xc3\xa9\",1.123457],\"z\":0}\n");
    const double invalid[]={1000000000.1,std::numeric_limits<double>::infinity(),std::numeric_limits<double>::quiet_NaN()};
    for(int i=0;i<3;++i){bool failed=false;try{oracle::canonical(json::Value(invalid[i]));}catch(const oracle::Error& e){failed=e.code=="state_unavailable";}require(failed);}
    oracle::validateFilename("checkpoint_001-abc.json");
    const char* invalidNames[]={"../state.json","a/b.json","a\\b.json","a.json:stream","NUL.json","COM1.json","LPT9.json",".json","a.JSON","a.json.","a\n.json","x y.json"};
    for(int i=0;i<12;++i)badFilename(invalidNames[i]);
    std::cout<<"{\"passed\":true,\"checks\":"<<checks<<",\"toolset\":\"v100 x64\"}\n";return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}}
