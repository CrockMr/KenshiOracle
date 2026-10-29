// SPDX-License-Identifier: GPL-3.0-only
#pragma once
#include <istream>
#include <limits>
#include <string>

struct BootstrapActivation {
    enum Mode { Disabled, Until, Unlimited } mode;
    __int64 validUntil;
    BootstrapActivation():mode(Disabled),validUntil(0){}
    bool active(__int64 now) const {
        return mode==Unlimited||(mode==Until&&now>=0&&now<validUntil);
    }
};

inline bool bootstrapWhitespace(char c){
    return c==' '||c=='\t'||c=='\r'||c=='\n'||c=='\f'||c=='\v';
}

inline BootstrapActivation parseBootstrapActivation(const std::string& text){
    BootstrapActivation activation;
    if(text.empty()||text.size()>64)return activation;
    size_t first=0,last=text.size();
    while(first<last&&bootstrapWhitespace(text[first]))++first;
    while(last>first&&bootstrapWhitespace(text[last-1]))--last;
    if(first==last)return activation;
    const std::string token=text.substr(first,last-first);
    if(token=="unlimited"){
        activation.mode=BootstrapActivation::Unlimited;
        return activation;
    }
    if(token.size()>19)return activation;
    const __int64 maximum=(std::numeric_limits<__int64>::max)();
    __int64 value=0;
    for(size_t i=0;i<token.size();++i){
        if(token[i]<'0'||token[i]>'9')return activation;
        const int digit=token[i]-'0';
        if(value>(maximum-digit)/10)return activation;
        value=value*10+digit;
    }
    if(value<=0)return activation;
    activation.mode=BootstrapActivation::Until;
    activation.validUntil=value;
    return activation;
}

inline BootstrapActivation readBootstrapActivation(std::istream& input){
    std::string text;
    char c;
    while(input.get(c)){
        text+=c;
        if(text.size()>64)return BootstrapActivation();
    }
    if(input.bad()||(!input.eof()&&input.fail()))return BootstrapActivation();
    return parseBootstrapActivation(text);
}
