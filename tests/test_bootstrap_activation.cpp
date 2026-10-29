// SPDX-License-Identifier: GPL-3.0-only
#include <iostream>
#include <sstream>
#include <stdexcept>
#include "../plugin/BootstrapActivation.h"
static int checks=0;
static void require(bool condition){++checks;if(!condition)throw std::runtime_error("bootstrap activation assertion");}
static void disabled(const std::string& text){
    BootstrapActivation a=parseBootstrapActivation(text);
    require(a.mode==BootstrapActivation::Disabled&&a.validUntil==0&&!a.active(0)&&!a.active(1793225700));
    std::istringstream stream(text);BootstrapActivation b=readBootstrapActivation(stream);
    require(b.mode==a.mode&&b.validUntil==a.validUntil);
}
int main(){try{
    require(_MSC_VER==1600&&sizeof(void*)==8);
    const __int64 limit=(std::numeric_limits<__int64>::max)();
    BootstrapActivation a=parseBootstrapActivation("1793225700");
    require(a.mode==BootstrapActivation::Until&&a.validUntil==1793225700);
    require(a.active(1793225699)&&!a.active(1793225700)&&!a.active(1793225701));
    require(!a.active(-1));
    a=parseBootstrapActivation(" \t1793225700\r\n");require(a.mode==BootstrapActivation::Until&&a.active(1793225699));
    a=parseBootstrapActivation("0000000000000000001");require(a.validUntil==1&&a.active(0)&&!a.active(1));
    a=parseBootstrapActivation("9223372036854775807");require(a.validUntil==limit&&a.active(limit-1)&&!a.active(limit));
    a=parseBootstrapActivation("unlimited");require(a.mode==BootstrapActivation::Unlimited&&a.validUntil==0);
    require(a.active(0)&&a.active(1793225700)&&a.active(limit));
    std::istringstream spaces("\r\n\t unlimited \n");a=readBootstrapActivation(spaces);
    require(a.mode==BootstrapActivation::Unlimited&&a.active(limit));
    a=parseBootstrapActivation(std::string(55,' ')+"unlimited");require(a.mode==BootstrapActivation::Unlimited);
    const char* invalid[]={""," ","0","-1","+1793225700","1.0","1e10","0x123","unlimited later","1793225700 unlimited",
        "1793225700x","Unlimited","UNLIMITED","null","false","-9223372036854775808","9223372036854775808","18446744073709551615","10000000000000000000"};
    for(size_t i=0;i<sizeof(invalid)/sizeof(*invalid);++i)disabled(invalid[i]);
    disabled(std::string("unlimited\0",10));disabled(std::string("1793225700\0",11));disabled(std::string(56,' ')+"unlimited");
    disabled(std::string("\xEF\xBB\xBF")+"unlimited");
    std::istringstream missing;missing.setstate(std::ios::failbit);require(readBootstrapActivation(missing).mode==BootstrapActivation::Disabled);
    std::istringstream corrupt("unlimited");corrupt.setstate(std::ios::badbit);require(readBootstrapActivation(corrupt).mode==BootstrapActivation::Disabled);
    std::istringstream longInput(std::string(100000,'x'));require(readBootstrapActivation(longInput).mode==BootstrapActivation::Disabled);
    require(longInput.tellg()==(std::streamoff)65); // Bounded input consumption, even for an oversized file.
    std::cout<<"{\"passed\":true,\"checks\":"<<checks<<",\"toolset\":\"v100 x64\",\"unlimited_explicit\":true,\"bounded_input_bytes\":64}\n";
    return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}}
