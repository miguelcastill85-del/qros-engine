#include "qros/sha256.hpp"

#include <algorithm>
#include <array>
#include <fstream>
#include <limits>
#include <stdexcept>

namespace qros {
namespace {
using u32 = std::uint32_t;
constexpr std::array<u32,64> K = {
0x428a2f98u,0x71374491u,0xb5c0fbcfu,0xe9b5dba5u,0x3956c25bu,0x59f111f1u,0x923f82a4u,0xab1c5ed5u,
0xd807aa98u,0x12835b01u,0x243185beu,0x550c7dc3u,0x72be5d74u,0x80deb1feu,0x9bdc06a7u,0xc19bf174u,
0xe49b69c1u,0xefbe4786u,0x0fc19dc6u,0x240ca1ccu,0x2de92c6fu,0x4a7484aau,0x5cb0a9dcu,0x76f988dau,
0x983e5152u,0xa831c66du,0xb00327c8u,0xbf597fc7u,0xc6e00bf3u,0xd5a79147u,0x06ca6351u,0x14292967u,
0x27b70a85u,0x2e1b2138u,0x4d2c6dfcu,0x53380d13u,0x650a7354u,0x766a0abbu,0x81c2c92eu,0x92722c85u,
0xa2bfe8a1u,0xa81a664bu,0xc24b8b70u,0xc76c51a3u,0xd192e819u,0xd6990624u,0xf40e3585u,0x106aa070u,
0x19a4c116u,0x1e376c08u,0x2748774cu,0x34b0bcb5u,0x391c0cb3u,0x4ed8aa4au,0x5b9cca4fu,0x682e6ff3u,
0x748f82eeu,0x78a5636fu,0x84c87814u,0x8cc70208u,0x90befffau,0xa4506cebu,0xbef9a3f7u,0xc67178f2u};
inline u32 rotr(u32 x,u32 n){return (x>>n)|(x<<(32-n));}
}

Sha256Builder::Sha256Builder()
    : h_{0x6a09e667u,0xbb67ae85u,0x3c6ef372u,0xa54ff53au,0x510e527fu,0x9b05688cu,0x1f83d9abu,0x5be0cd19u} {}

void Sha256Builder::block(const std::uint8_t* p) {
    u32 w[64]{};
    for(std::size_t i=0;i<16;++i) w[i]=(u32(p[4*i])<<24)|(u32(p[4*i+1])<<16)|(u32(p[4*i+2])<<8)|u32(p[4*i+3]);
    for(std::size_t i=16;i<64;++i){u32 s0=rotr(w[i-15],7)^rotr(w[i-15],18)^(w[i-15]>>3);u32 s1=rotr(w[i-2],17)^rotr(w[i-2],19)^(w[i-2]>>10);w[i]=w[i-16]+s0+w[i-7]+s1;}
    u32 a=h_[0],b=h_[1],c=h_[2],d=h_[3],e=h_[4],f=h_[5],g=h_[6],hh=h_[7];
    for(std::size_t i=0;i<64;++i){u32 S1=rotr(e,6)^rotr(e,11)^rotr(e,25);u32 ch=(e&f)^((~e)&g);u32 t1=hh+S1+ch+K[i]+w[i];u32 S0=rotr(a,2)^rotr(a,13)^rotr(a,22);u32 maj=(a&b)^(a&c)^(b&c);u32 t2=S0+maj;hh=g;g=f;f=e;e=d+t1;d=c;c=b;b=a;a=t1+t2;}
    h_[0]+=a;h_[1]+=b;h_[2]+=c;h_[3]+=d;h_[4]+=e;h_[5]+=f;h_[6]+=g;h_[7]+=hh;
}

void Sha256Builder::update(const void* data, std::size_t size) {
    if (finished_) throw std::logic_error("Sha256Builder update after finish");
    const auto* p = static_cast<const std::uint8_t*>(data);
    if (size > std::numeric_limits<u64>::max() - total_) throw std::overflow_error("SHA-256 input length overflow");
    total_ += static_cast<u64>(size);
    while(size){
        const std::size_t take=std::min(size,64-used_);
        std::copy(p,p+take,buf_.begin()+static_cast<std::ptrdiff_t>(used_));
        used_+=take;p+=take;size-=take;
        if(used_==64){block(buf_.data());used_=0;}
    }
}

void Sha256Builder::update(std::string_view text) { update(text.data(), text.size()); }

std::string Sha256Builder::finish() {
    if (finished_) throw std::logic_error("Sha256Builder finish called twice");
    finished_ = true;
    if (total_ > std::numeric_limits<u64>::max() / 8ULL) throw std::overflow_error("SHA-256 bit length overflow");
    const u64 bits=total_*8ULL;
    buf_[used_++]=0x80;
    if(used_>56){while(used_<64)buf_[used_++]=0;block(buf_.data());used_=0;}
    while(used_<56)buf_[used_++]=0;
    for(int i=7;i>=0;--i)buf_[used_++]=std::uint8_t((bits>>(i*8))&0xffULL);
    block(buf_.data());
    static constexpr char HEX[] = "0123456789abcdef";
    std::string out(64, '0');
    std::size_t pos = 0;
    for (const auto x : h_) {
        for (int shift = 28; shift >= 0; shift -= 4) {
            out[pos++] = HEX[(x >> static_cast<unsigned>(shift)) & 0x0fu];
        }
    }
    return out;
}

std::string sha256_file(const std::filesystem::path& path){
    std::ifstream f(path,std::ios::binary);if(!f)throw std::runtime_error("cannot open for sha256: "+path.string());
    Sha256Builder s;std::array<char,1<<16> b{};
    while(f){f.read(b.data(),static_cast<std::streamsize>(b.size()));auto n=f.gcount();if(n>0)s.update(b.data(),static_cast<std::size_t>(n));}
    if (!f.eof() && f.fail()) throw std::runtime_error("I/O error while hashing: "+path.string());
    return s.finish();
}
std::string sha256_text(std::string_view text){Sha256Builder s;s.update(text);return s.finish();}

} // namespace qros
