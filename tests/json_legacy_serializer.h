// SPDX-License-Identifier: GPL-3.0-only
// Frozen OWN serializer from KenshiProbe 0.8.11; byte-compatibility reference only.
#pragma once
#include "../plugin/json.h"
namespace json_legacy {
inline std::string dump(const json::Value& v) {
    typedef json::Value Value;
    std::ostringstream o;o.imbue(std::locale::classic());
    if(v.type==Value::NIL)return "null";if(v.type==Value::BOOL)return v.boolean?"true":"false";
    if(v.type==Value::NUMBER){if(!_finite(v.number))return "null";o.precision(16);o<<v.number;return o.str();}
    if(v.type==Value::STRING){o<<'"';const char* hex="0123456789abcdef";for(size_t i=0;i<v.str.size();++i){unsigned char c=v.str[i];if(c=='"'||c=='\\')o<<'\\'<<(char)c;else if(c<32)o<<"\\u00"<<hex[c>>4]<<hex[c&15];else o<<(char)c;}o<<'"';return o.str();}
    if(v.type==Value::OBJECT){o<<'{';bool first=true;for(std::map<std::string,Value>::const_iterator i=v.object.begin();i!=v.object.end();++i){if(!first)o<<',';first=false;o<<json_legacy::dump(Value(i->first))<<':'<<json_legacy::dump(i->second);}o<<'}';}
    else{o<<'[';for(size_t i=0;i<v.array.size();++i){if(i)o<<',';o<<json_legacy::dump(v.array[i]);}o<<']';}return o.str();
}
}
