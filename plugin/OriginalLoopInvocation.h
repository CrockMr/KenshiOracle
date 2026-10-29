// SPDX-License-Identifier: GPL-3.0-only
#pragma once
// Exact x64 SDK argument forwarding, independently testable without game code.
template<typename World> struct OriginalLoopInvocation {
    void (*original)(World*,float);
    World* world;
    float dt;
    void operator()()const{original(world,dt);}
};
