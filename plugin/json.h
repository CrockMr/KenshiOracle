// SPDX-License-Identifier: GPL-3.0-only
#pragma once
#include <string>
#include <map>
#include <vector>
#include <stdexcept>
#include <sstream>
#include <cstdlib>
#include <cmath>
#include <float.h>
#include <locale>
#include <algorithm>
namespace json {
struct Value {
    enum Type { NIL, BOOL, NUMBER, STRING, OBJECT, ARRAY } type;
    bool boolean; double number; std::string str;
    std::map<std::string, Value> object; std::vector<Value> array;
    Value():type(NIL),boolean(false),number(0) {}
    explicit Value(double n):type(NUMBER),boolean(false),number(n) {}
    explicit Value(const std::string& s):type(STRING),boolean(false),number(0),str(s) {}
    static Value obj() { Value v; v.type=OBJECT; return v; }
    static Value arr() { Value v; v.type=ARRAY; return v; }
    static Value flag(bool b) { Value v; v.type=BOOL; v.boolean=b; return v; }
    // Transfer every field, including inactive payloads. All containers use the
    // default allocator inside this module; swapping does not clone their trees.
    void swap(Value& other){
        if(this==&other)return;
        std::swap(type,other.type);std::swap(boolean,other.boolean);std::swap(number,other.number);
        str.swap(other.str);object.swap(other.object);array.swap(other.array);
    }
    const Value& at(const std::string& key) const {
        std::map<std::string,Value>::const_iterator i=object.find(key);
        if(type!=OBJECT || i==object.end()) throw std::runtime_error("missing field");
        return i->second;
    }
};
class Parser {
    const std::string& s; size_t p;
    void ws() { while(p<s.size() && (s[p]==' '||s[p]=='\r'||s[p]=='\n'||s[p]=='\t')) ++p; }
    char take() { if(p>=s.size()) throw std::runtime_error("truncated JSON"); return s[p++]; }
    void expect(char c) { if(take()!=c) throw std::runtime_error("invalid JSON"); }
    unsigned hex() { unsigned v=0; for(int i=0;i<4;++i) {char c=take(); v*=16; if(c>='0'&&c<='9')v+=c-'0';else if(c>='a'&&c<='f')v+=c-'a'+10;else if(c>='A'&&c<='F')v+=c-'A'+10;else throw std::runtime_error("bad unicode");}return v; }
    void utf8(std::string& o,unsigned v) { if(v<128)o+=(char)v;else if(v<2048){o+=(char)(192|(v>>6));o+=(char)(128|(v&63));}else if(v<65536){o+=(char)(224|(v>>12));o+=(char)(128|((v>>6)&63));o+=(char)(128|(v&63));}else{o+=(char)(240|(v>>18));o+=(char)(128|((v>>12)&63));o+=(char)(128|((v>>6)&63));o+=(char)(128|(v&63));} }
    std::string string() {
        expect('"'); std::string o;
        for(;;) { unsigned char c=take(); if(c=='"')return o; if(c<32)throw std::runtime_error("control character");
            if(c!='\\'){o+=(char)c;continue;} c=take();
            switch(c){case '"':case '\\':case '/':o+=(char)c;break;case 'b':o+='\b';break;case 'f':o+='\f';break;case 'n':o+='\n';break;case 'r':o+='\r';break;case 't':o+='\t';break;
            case 'u': {unsigned v=hex();if(v>=0xD800&&v<=0xDBFF){expect('\\');expect('u');unsigned lo=hex();if(lo<0xDC00||lo>0xDFFF)throw std::runtime_error("bad surrogate");v=65536+((v-0xD800)<<10)+lo-0xDC00;}else if(v>=0xDC00&&v<=0xDFFF)throw std::runtime_error("bad surrogate");utf8(o,v);break;}
            default:throw std::runtime_error("bad escape");}
        }
    }
    Value value(int depth) {
        if(depth>16)throw std::runtime_error("JSON too deep");ws(); if(p==s.size())throw std::runtime_error("empty JSON");char c=s[p];
        if(c=='"')return Value(string());
        if(c=='{'||c=='['){++p;Value v=c=='{'?Value::obj():Value::arr();ws();char end=c=='{'?'}':']';if(p<s.size()&&s[p]==end){++p;return v;}for(;;){ws();if(c=='{'){std::string k=string();ws();expect(':');if(v.object.count(k))throw std::runtime_error("duplicate key");v.object[k]=value(depth+1);}else v.array.push_back(value(depth+1));ws();char next=take();if(next==end)return v;if(next!=',')throw std::runtime_error("expected comma");}}
        if(c=='t'||c=='f'||c=='n'){const char* word=c=='t'?"true":c=='f'?"false":"null";for(const char* t=word;*t;++t)expect(*t);return c=='n'?Value():Value::flag(c=='t');}
        size_t begin=p;if(c=='-')++p;if(p>=s.size())throw std::runtime_error("bad number");if(s[p]=='0')++p;else{if(s[p]<'1'||s[p]>'9')throw std::runtime_error("bad number");while(p<s.size()&&s[p]>='0'&&s[p]<='9')++p;}
        if(p<s.size()&&s[p]=='.'){++p;size_t b=p;while(p<s.size()&&s[p]>='0'&&s[p]<='9')++p;if(p==b)throw std::runtime_error("bad fraction");}
        if(p<s.size()&&(s[p]=='e'||s[p]=='E')){++p;if(p<s.size()&&(s[p]=='+'||s[p]=='-'))++p;size_t b=p;while(p<s.size()&&s[p]>='0'&&s[p]<='9')++p;if(p==b)throw std::runtime_error("bad exponent");}
        double n=std::strtod(s.substr(begin,p-begin).c_str(),0);if(!_finite(n))throw std::runtime_error("non finite");return Value(n);
    }
public: explicit Parser(const std::string& input):s(input),p(0){} Value parse(){Value v=value(0);ws();if(p!=s.size())throw std::runtime_error("trailing JSON");return v;}
};
inline void appendQuoted(std::string& out,const std::string& value){
    out+='"';const char* hex="0123456789abcdef";
    for(size_t i=0;i<value.size();++i){unsigned char c=value[i];
        if(c=='"'||c=='\\'){out+='\\';out+=(char)c;}
        else if(c<32){out+="\\u00";out+=hex[c>>4];out+=hex[c&15];}
        else out+=(char)c;
    }out+='"';
}
inline void appendSerialized(std::string& out,const Value& v){
    if(v.type==Value::NIL){out+="null";return;}
    if(v.type==Value::BOOL){out+=v.boolean?"true":"false";return;}
    if(v.type==Value::NUMBER){
        if(!_finite(v.number)){out+="null";return;}
        // Keep the exact v100 number formatting and precision of 0.8.11.
        std::ostringstream number;number.imbue(std::locale::classic());number.precision(16);number<<v.number;out+=number.str();return;
    }
    if(v.type==Value::STRING){appendQuoted(out,v.str);return;}
    if(v.type==Value::OBJECT){out+='{';bool first=true;
        for(std::map<std::string,Value>::const_iterator i=v.object.begin();i!=v.object.end();++i){if(!first)out+=',';first=false;appendQuoted(out,i->first);out+=':';appendSerialized(out,i->second);}
        out+='}';
    }else{out+='[';for(size_t i=0;i<v.array.size();++i){if(i)out+=',';appendSerialized(out,v.array[i]);}out+=']';}
}
inline std::string dump(const Value& v) {
    std::string out;out.reserve(512);appendSerialized(out,v);return out;
}
}
