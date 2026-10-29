// SPDX-License-Identifier: GPL-3.0-only
// Compile with VC++ 2010 x64. Exercises the exact parser shipped in the DLL.
#include "../plugin/json.h"
#include <iostream>
#include <limits>
#include "json_legacy_serializer.h"
static void require(bool ok) { if(!ok) throw std::runtime_error("test assertion failed"); }
static unsigned long randomState=12345;
static unsigned long next(){randomState=randomState*1664525ul+1013904223ul;return randomState;}
static json::Value tree(int depth){
    unsigned long kind=next()%(depth?6:4);
    if(kind==0)return json::Value();if(kind==1)return json::Value::flag(next()%2!=0);
    if(kind==2)return json::Value(((int)(next()%1000000)-500000)/13.0);
    if(kind==3){std::string s;for(int i=0;i<12;++i)s+=(char)(next()%256);return json::Value(s);}
    json::Value v=kind==4?json::Value::obj():json::Value::arr();
    for(int i=0;i<3;++i){if(kind==4){std::ostringstream key;key<<i<<"\n\"\\";v.object[key.str()]=tree(depth-1);}else v.array.push_back(tree(depth-1));}return v;
}
struct Comma :std::numpunct<char>{protected:char do_decimal_point()const{return ',';}};
int main() {
    try {
        json::Value v=json::Parser("{\"id\":\"test\",\"params\":{\"paused\":false,\"speed\":2.5},\"command\":\"ping\"}").parse();
        require(v.at("id").str=="test");require(v.at("params").at("paused").type==json::Value::BOOL);
        require(!v.at("params").at("paused").boolean);require(v.at("params").at("speed").number==2.5);
        json::Value unicode=json::Parser("\"\\u00e9\\ud83d\\ude00\"").parse();
        require(unicode.str==std::string("\xc3\xa9\xf0\x9f\x98\x80"));
        require(json::Parser(json::dump(v)).parse().at("params").at("speed").number==2.5);
        const char* invalid[]={"", "{", "null null", "01", "1.", "1e", "1e999", "NaN", "{\"id\":1,\"id\":2}", "[1,]", "{\"a\":1,}", "\"\\ud800\"", "\"\\udc00\"", "\"\\x\"", "\"\n\"", "[[[[[[[[[[[[[[[[[[0]]]]]]]]]]]]]]]]]]"};
        for(size_t i=0;i<sizeof(invalid)/sizeof(invalid[0]);++i){bool failed=false;try{json::Parser(invalid[i]).parse();}catch(const std::exception&){failed=true;}require(failed);}
        std::string bytes;for(int i=0;i<256;++i)bytes+=(char)i;
        json::Value binary(bytes);require(json::dump(binary)==json_legacy::dump(binary));
        json::Value keys=json::Value::obj();keys.object[bytes]=binary;keys.object[""]=json::Value::arr();
        require(json::dump(keys)==json_legacy::dump(keys));
        double edges[]={0.0,-0.0,1.0,-1.0,1e-20,1e20,std::numeric_limits<double>::max(),std::numeric_limits<double>::min(),
            std::numeric_limits<double>::denorm_min(),std::numeric_limits<double>::infinity(),-std::numeric_limits<double>::infinity(),std::numeric_limits<double>::quiet_NaN()};
        std::locale prior=std::locale();std::locale::global(std::locale(prior,new Comma));
        for(size_t i=0;i<sizeof(edges)/sizeof(edges[0]);++i)require(json::dump(json::Value(edges[i]))==json_legacy::dump(json::Value(edges[i])));
        for(int i=0;i<10000;++i){double n=((int)(next()%100000000)-50000000)/17.0;require(json::dump(json::Value(n))==json_legacy::dump(json::Value(n)));}
        std::locale::global(prior);
        for(int i=0;i<1000;++i){json::Value generated=tree(5);require(json::dump(generated)==json_legacy::dump(generated));}
        for(int n=65534;n<=65537;++n){json::Value large(std::string(n,'x'));require(json::dump(large)==json_legacy::dump(large));}
        std::string prefix="prefix:";json::appendSerialized(prefix,v);require(prefix=="prefix:"+json_legacy::dump(v));
        std::cout<<"Native JSON checks passed (v100 x64)\n";return 0;
    } catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}
}
