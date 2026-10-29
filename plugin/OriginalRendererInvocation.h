// SPDX-License-Identifier: GPL-3.0-only
#pragma once
// Exact x64 SDK forwarding, independently testable without game code.
template<typename RendererType> struct OriginalRendererInvocation {
    void (*original)(RendererType*);
    RendererType* renderer;
    void operator()()const{original(renderer);}
};
