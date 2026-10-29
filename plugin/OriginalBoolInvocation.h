// SPDX-License-Identifier: GPL-3.0-only
#pragma once
template<typename Object> struct OriginalBoolInvocation {
    bool (*original)(Object*);
    Object* object;
    mutable bool result;
    void operator()()const{result=original(object);}
};
