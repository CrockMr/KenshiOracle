// SPDX-License-Identifier: GPL-3.0-only
#pragma once
#include "json.h"
#include <iomanip>
#include <cctype>

// Engine-independent canonical JSON. The state contract uses the same binary64
// quantisation in Python: floor(abs(x) * 1e6 + .5), ties away from zero.
namespace oracle {
struct Error : std::runtime_error {
    std::string code;
    Error(const char* c,const std::string& message):std::runtime_error(message),code(c){}
};
inline const json::Value& field(const json::Value& p,const char* name){
    if(p.type!=json::Value::OBJECT||!p.object.count(name))throw Error("invalid_request",std::string("missing field: ")+name);
    return p.at(name);
}
inline double number(const json::Value& p,const char* name,double low,double high){
    const json::Value& v=field(p,name);
    if(v.type!=json::Value::NUMBER||!_finite(v.number)||v.number<low||v.number>high)throw Error("invalid_request",std::string("invalid number: ")+name);
    return v.number;
}
inline std::string text(const json::Value& p,const char* name,size_t maximum=512){
    const json::Value& v=field(p,name);
    if(v.type!=json::Value::STRING||v.str.empty()||v.str.size()>maximum||v.str.find('\0')!=std::string::npos)throw Error("invalid_request",std::string("invalid string: ")+name);
    return v.str;
}
inline bool flag(const json::Value& p,const char* name){
    const json::Value& v=field(p,name);if(v.type!=json::Value::BOOL)throw Error("invalid_request",std::string("invalid boolean: ")+name);return v.boolean;
}
inline void keys(const json::Value& p,const char* const* allowed,size_t n){
    if(p.type!=json::Value::OBJECT)throw Error("invalid_request","params must be object");
    for(std::map<std::string,json::Value>::const_iterator i=p.object.begin();i!=p.object.end();++i){
        bool found=false;for(size_t j=0;j<n;++j)if(i->first==allowed[j])found=true;
        if(!found)throw Error("invalid_request",std::string("unknown parameter: ")+i->first);
    }
}
inline void appendNumber(std::string& out,double value){
    if(!_finite(value)||fabs(value)>1e9)throw Error("state_unavailable","state number is non-finite or outside canonical range");
    double magnitude=floor(fabs(value)*1000000.0+0.5);
    unsigned __int64 q=(unsigned __int64)magnitude;
    if(value<0&&q)out+='-';
    std::ostringstream whole;whole.imbue(std::locale::classic());whole<<(q/1000000);out+=whole.str();
    unsigned int fraction=(unsigned int)(q%1000000);
    if(fraction){std::ostringstream digits;digits.imbue(std::locale::classic());digits<<std::setw(6)<<std::setfill('0')<<fraction;std::string s=digits.str();while(!s.empty()&&s[s.size()-1]=='0')s.erase(s.size()-1);out+='.';out+=s;}
}
inline void appendCanonicalQuoted(std::string& out,const std::string& value){
    // Match Python json.dumps(..., ensure_ascii=False), including its five
    // short control escapes. The legacy wire serializer remains unchanged.
    out+='"';const char* hex="0123456789abcdef";
    for(size_t i=0;i<value.size();++i){unsigned char c=value[i];
        if(c=='"'||c=='\\'){out+='\\';out+=(char)c;}
        else if(c=='\b')out+="\\b";else if(c=='\t')out+="\\t";else if(c=='\n')out+="\\n";else if(c=='\f')out+="\\f";else if(c=='\r')out+="\\r";
        else if(c<32){out+="\\u00";out+=hex[c>>4];out+=hex[c&15];}
        else out+=(char)c;
    }out+='"';
}
inline void appendCanonical(std::string& out,const json::Value& v){
    if(v.type==json::Value::NUMBER){appendNumber(out,v.number);return;}
    if(v.type==json::Value::NIL){out+="null";return;}
    if(v.type==json::Value::BOOL){out+=v.boolean?"true":"false";return;}
    if(v.type==json::Value::STRING){appendCanonicalQuoted(out,v.str);return;}
    if(v.type==json::Value::OBJECT){out+='{';bool first=true;for(std::map<std::string,json::Value>::const_iterator i=v.object.begin();i!=v.object.end();++i){if(!first)out+=',';first=false;appendCanonicalQuoted(out,i->first);out+=':';appendCanonical(out,i->second);}out+='}';return;}
    out+='[';for(size_t i=0;i<v.array.size();++i){if(i)out+=',';appendCanonical(out,v.array[i]);}out+=']';
}
inline std::string canonical(const json::Value& v){std::string out;out.reserve(16384);appendCanonical(out,v);out+='\n';return out;}
inline json::Value finiteOrNull(double value){return _finite(value)&&fabs(value)<=1e9?json::Value(value):json::Value();}
inline void validateFilename(const std::string& name){
    if(name.size()<6||name.size()>105||name.substr(name.size()-5)!=".json"||name.substr(0,name.size()-5).find_first_not_of("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")!=std::string::npos)
        throw Error("invalid_request","filename must be a simple name ending in .json");
    std::string stem=name.substr(0,name.size()-5);for(size_t i=0;i<stem.size();++i)stem[i]=(char)toupper((unsigned char)stem[i]);
    if(stem=="CON"||stem=="PRN"||stem=="AUX"||stem=="NUL"||(stem.size()==4&&(stem.substr(0,3)=="COM"||stem.substr(0,3)=="LPT")&&stem[3]>='0'&&stem[3]<='9'))throw Error("invalid_request","reserved filename");
}
}
