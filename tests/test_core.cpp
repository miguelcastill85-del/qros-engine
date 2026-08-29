#include "qros/core.hpp"
#include "qros/custody.hpp"
#include "qros/qdata.hpp"
#include "qros/sha256.hpp"
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <stdexcept>
#include <iostream>
#include <limits>
#include <random>
#include <vector>
using namespace qros;
#define REQUIRE(x) do { if(!(x)){ std::cerr<<"REQUIRE failed at "<<__FILE__<<":"<<__LINE__<<": " #x "\n"; return 1; } } while(0)
static Tick T(u64 seq,i64 ts,i64 day,i64 bid,i64 ask){return Tick{seq,ts,day,bid,ask};}
int main(){
    const i64 D=20260827;
    {
        std::vector<Tick> v{T(1,100,D,1000,1010),T(2,101,D,1005,1015),T(3,102,D,1115,1125)};
        Intent x{"BUY_TP",std::string(64,'0'),Side::Buy,1,100,D,3,100,100}; auto t=replay_market_after_signal(v,x);
        REQUIRE(t.entered && t.entry_price_u==1015 && t.exit_price_u==1115 && t.reason==ExitReason::TakeProfit && t.pnl_u==100 && t.r_num==100 && t.r_den==100);
    }
    {
        std::vector<Tick> v{T(1,100,D,1000,1010),T(2,101,D,1005,1015),T(3,102,D,895,905)};
        Intent x{"SELL_TP",std::string(64,'0'),Side::Sell,1,100,D,3,100,100}; auto t=replay_market_after_signal(v,x);
        REQUIRE(t.entered && t.entry_price_u==1005 && t.exit_price_u==905 && t.reason==ExitReason::TakeProfit && t.pnl_u==100);
    }
    {
        std::vector<Tick> v{T(1,100,D,1000,1010),T(2,101,D,1005,1005),T(3,102,D,1010,1020),T(4,103,D,910,920)};
        Intent x{"ZERO_SKIP",std::string(64,'0'),Side::Buy,1,100,D,4,100,1000}; auto t=replay_market_after_signal(v,x); REQUIRE(t.entry_seq==3 && t.entry_price_u==1020);
    }
    {
        std::vector<Tick> v{T(1,100,D,1000,1010),T(2,101,D,1000,1010),T(3,102,D,850,860)};
        Intent x{"GAP_SL",std::string(64,'0'),Side::Buy,1,100,D,3,100,1000}; auto t=replay_market_after_signal(v,x); REQUIRE(t.reason==ExitReason::StopLoss && t.exit_price_u==850 && t.pnl_u==-160);
    }
    {
        // Same timestamp is allowed if seq is later: seq is the causal authority.
        std::vector<Tick> v{T(1,100,D,1000,1010),T(2,100,D,1001,1011),T(3,100,D,1002,1012),T(4,101,D,1003,1013)};
        Intent x{"SEQ_CAUSAL",std::string(64,'0'),Side::Buy,2,100,D,4,1000,1000}; auto t=replay_market_after_signal(v,x); REQUIRE(t.entry_seq==3);
    }
    {
        std::vector<Tick> v{T(1,100,D,1000,1010),T(2,101,D,1005,1015),T(3,102,D,1020,1030),T(4,103,D+1,2000,2010)};
        Intent x{"DAY_CLOSE",std::string(64,'0'),Side::Buy,1,100,D,3,1000,1000}; auto t=replay_market_after_signal(v,x); REQUIRE(t.reason==ExitReason::SessionClose && t.exit_seq==3 && t.exit_price_u==1020 && t.pnl_u==5);
    }
    {
        std::vector<Tick> v{T(1,100,D,1010,1000),T(2,101,D,1000,1010)}; Intent x{"CROSSED",std::string(64,'0'),Side::Buy,1,100,D,2,100,100};
        auto a=audit_ticks(v); auto t=replay_market_after_signal(v,x); REQUIRE(!a.pass && a.crossed_market==1 && t.reason==ExitReason::DataError);
    }
    {
        std::vector<Tick> v{T(2,100,D,1000,1010),T(2,101,D,1000,1010)}; auto a=audit_ticks(v); REQUIRE(!a.pass && a.seq_errors==1);
    }
    {
        // Overflow cannot become UB or a fabricated level.
        std::vector<Tick> v{T(1,100,D,std::numeric_limits<i64>::max()-20,std::numeric_limits<i64>::max()-10),T(2,101,D,std::numeric_limits<i64>::max()-20,std::numeric_limits<i64>::max()-10)};
        Intent x{"OVERFLOW",std::string(64,'0'),Side::Buy,1,100,D,2,100,100}; auto t=replay_market_after_signal(v,x); REQUIRE(t.reason==ExitReason::DataError && !t.entered);
    }
    {
        // Signal metadata must bind exactly to the authoritative signal record.
        const auto low=std::numeric_limits<i64>::min();
        const auto high=std::numeric_limits<i64>::max();
        std::vector<Tick> v{T(1,100,D,low+10,low+11),T(2,101,D,low+12,low+13),T(3,102,D,high-1,high)};
        Intent x{"PNL_OVERFLOW",std::string(64,'0'),Side::Buy,1,100,D,3,1,1};
        const auto t=replay_market_after_signal(v,x);
        REQUIRE(t.reason==ExitReason::DataError && !t.entered);
    }
    {
        // Signal metadata must bind exactly to the authoritative signal record.
        std::vector<Tick> v{T(1,100,D,1000,1010),T(2,101,D,1005,1015),T(3,102,D,1010,1020)};
        Intent x{"BAD_SIGNAL_BOUNDARY",std::string(64,'0'),Side::Buy,1,999,D,3,100,100};
        auto t=replay_market_after_signal(v,x); REQUIRE(t.reason==ExitReason::DataError && !t.entered);
    }
    {
        // A truncated session cannot masquerade as an authoritative same-day close.
        std::vector<Tick> v{T(1,100,D,1000,1010),T(2,101,D,1005,1015)};
        Intent x{"MISSING_CLOSE_BOUNDARY",std::string(64,'0'),Side::Buy,1,100,D,99,100,100};
        auto t=replay_market_after_signal(v,x); REQUIRE(t.reason==ExitReason::DataError && !t.entered);
    }
    {
        // If no executable quote exists after entry, never fabricate a same-tick exit.
        std::vector<Tick> v{T(1,100,D,1000,1010),T(2,101,D,1005,1015),T(3,102,D,1010,1010)};
        Intent x{"NO_POST_ENTRY_CLOSE",std::string(64,'0'),Side::Buy,1,100,D,3,1000,1000};
        auto t=replay_market_after_signal(v,x); REQUIRE(t.entered && t.reason==ExitReason::UnresolvedClose && t.exit_seq==0);
    }
    {
        // Repeated payloads are audited but not silently promoted to corruption: duplicate feed semantics require source authority.
        std::vector<Tick> v{T(1,100,D,1000,1010),T(2,100,D,1000,1010),T(3,101,D,1001,1011)};
        auto a=audit_ticks(v); REQUIRE(a.pass && a.same_timestamp==1 && a.repeated_quote_payload==1);
    }
    {
        // Streaming QDATA replay must be semantically identical to vector replay on exact bytes.
        const auto p = std::filesystem::temp_directory_path() / "qros_stream_semantic_test.csv";
        {
            std::ofstream f(p, std::ios::binary | std::ios::trunc);
            REQUIRE(static_cast<bool>(f));
            f << "seq,ts_ns,session_day,bid_u,ask_u\n"
              << "1,100,20260827,1000,1010\n"
              << "2,101,20260827,1005,1015\n"
              << "3,102,20260827,1115,1125\n";
        }
        const auto h = sha256_file(p);
        Intent x{"STREAM_EQ",h,Side::Buy,1,100,D,3,100,100};
        const auto v = read_ticks_csv_bound(p,h);
        const auto a = replay_market_after_signal(v,x);
        const auto b = replay_qdata_stream_bound(p,h,x);
        REQUIRE(a.entered==b.entered && a.entry_seq==b.entry_seq && a.entry_price_u==b.entry_price_u &&
                a.exit_seq==b.exit_seq && a.exit_price_u==b.exit_price_u && a.reason==b.reason && a.pnl_u==b.pnl_u &&
                a.r_num==b.r_num && a.r_den==b.r_den);
        std::filesystem::remove(p);
    }
    {
        // A TP/SL before EOF must NOT allow an early return that skips hashing the remaining bytes.
        const auto p = std::filesystem::temp_directory_path() / "qros_stream_full_hash_test.csv";
        {
            std::ofstream f(p, std::ios::binary | std::ios::trunc);
            REQUIRE(static_cast<bool>(f));
            f << "seq,ts_ns,session_day,bid_u,ask_u\n"
              << "1,100,20260827,1000,1010\n"
              << "2,101,20260827,1005,1015\n"
              << "3,102,20260827,1115,1125\n";
        }
        const auto old_hash = sha256_file(p);
        {
            std::ofstream f(p, std::ios::binary | std::ios::app);
            REQUIRE(static_cast<bool>(f));
            f << "4,103,20260828,1200,1210\n";
        }
        Intent x{"STREAM_HASH",old_hash,Side::Buy,1,100,D,3,100,100};
        bool rejected=false;
        try { (void)replay_qdata_stream_bound(p,old_hash,x); }
        catch (const std::runtime_error& e) { rejected = std::string(e.what()) == "DATA_AUTHORITY_HASH_MISMATCH"; }
        REQUIRE(rejected);
        std::filesystem::remove(p);
    }
    {
        // Deterministic property sweep: valid generated streams must preserve causal/session invariants.
        std::mt19937_64 rng(20260827ULL);
        for (int c=0; c<10000; ++c) {
            const int n = 6 + static_cast<int>(rng()%40ULL);
            std::vector<Tick> v; v.reserve(static_cast<std::size_t>(n));
            i64 ts=1000, px=100000 + static_cast<i64>(rng()%100000ULL);
            for(int i=0;i<n;++i){
                ts += static_cast<i64>(rng()%3ULL);
                px += static_cast<i64>(rng()%101ULL)-50;
                const i64 spr = (rng()%5ULL==0ULL)?0:static_cast<i64>(5 + (rng()%16ULL));
                v.push_back(T(static_cast<u64>(i+1),ts,D,px,px+spr));
            }
            const std::size_t si = static_cast<std::size_t>(rng()%static_cast<u64>(n-2));
            const std::size_t ci = si + 2 + static_cast<std::size_t>(rng()%static_cast<u64>(n-static_cast<int>(si)-2));
            const auto side = (rng()%2ULL)==0ULL ? Side::Buy : Side::Sell;
            Intent x{"PROP",std::string(64,'0'),side,v[si].seq,v[si].ts_ns,D,v[ci].seq,
                     20+static_cast<i64>(rng()%200ULL),20+static_cast<i64>(rng()%200ULL)};
            auto t=replay_market_after_signal(v,x);
            REQUIRE(t.reason!=ExitReason::DataError);
            if(t.entered){
                REQUIRE(t.entry_seq>x.signal_seq && t.entry_seq<=x.session_close_seq && t.entry_day==D);
                if(t.reason!=ExitReason::UnresolvedClose){
                    REQUIRE(t.exit_seq>t.entry_seq && t.exit_seq<=x.session_close_seq);
                }
                if(t.reason==ExitReason::TakeProfit || t.reason==ExitReason::StopLoss || t.reason==ExitReason::SessionClose){
                    REQUIRE(t.r_den==x.stop_distance_u);
                    REQUIRE(t.pnl_u==t.r_num);
                }
            } else {
                REQUIRE(t.reason==ExitReason::NoEntry);
            }
        }
    }
    
    {
        std::vector<qros::CustodyPartSpec> parts{
            {1, "SYNTH_SOURCE.part01.bin", 15, "ec740f84714c68ee42da209032db25f3ba758e70afcc93fb092959f1f7b7e50d"},
            {2, "SYNTH_SOURCE.part02.bin", 30, "22f38ae7453ce764a2239ef16a0f08923c85995e0e8c944e1bb00f8ce03574a8"},
            {3, "SYNTH_SOURCE.part03.bin", 15, "a69c5ca3f8fd9b188ba349a0d7074d0b0fe4377aaf56c35629f49ba860449f2a"}
        };
        REQUIRE(qros::custody_chain_root(parts)=="10668dda4aefea4cc8846573be7d4a702295da805065824a965f829611cbb7cd");
    }
std::cout<<"ALL_TESTS_PASS\n"; return 0;
}
