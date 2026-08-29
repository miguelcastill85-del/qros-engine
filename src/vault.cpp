#include "qros/pipeline.hpp"
#include "qros/sha256.hpp"
#include <chrono>
#include <fcntl.h>
#include <sys/file.h>
#include <unistd.h>

namespace qros::pipeline {
namespace {
Fields vault_policy(const std::filesystem::path& path,const std::string& hash) {
    auto f=read_fields(path,"QROS_VAULT_POLICY_V1",hash);
    exact_keys(f,{"dataset_spec_sha256","data_sha256","development_first_day","development_last_day",
        "holdout_first_day","holdout_last_day","exposure","authorization_id"});
    if(!hash_valid(f.at("dataset_spec_sha256"))||!hash_valid(f.at("data_sha256"))||!identifier(f.at("authorization_id"))) fail("VAULT_IDENTITY");
    const auto d0=integer(f.at("development_first_day")),d1=integer(f.at("development_last_day"));
    const auto h0=integer(f.at("holdout_first_day")),h1=integer(f.at("holdout_last_day"));
    if(d0<19700101||h0<19700101||d0>d1||h0>h1||!(d1<h0||h1<d0)) fail("VAULT_OVERLAPPING_PARTITIONS");
    if(f.at("exposure")!="SYNTHETIC"&&f.at("exposure")!="DEVELOPMENT_EXPOSED"&&f.at("exposure")!="HOLDOUT_SEALED") fail("VAULT_EXPOSURE");
    return f;
}
}
void enforce_vault(const DataSpec& data,const std::filesystem::path& policy,const std::string& policy_sha,const std::string& phase,const std::string& candidate_sha) {
    if(!hash_valid(candidate_sha)) fail("VAULT_CANDIDATE_BINDING_REQUIRED");
    const auto f=vault_policy(policy,policy_sha);
    if(f.at("dataset_spec_sha256")!=data.sha256||f.at("data_sha256")!=data.ticks_sha||f.at("exposure")!=data.exposure) fail("VAULT_DATA_OR_EXPOSURE_MISMATCH");
    if(phase!="DEVELOPMENT") fail("HOLDOUT_EXECUTION_REQUIRES_SEPARATE_SCIENTIFIC_DISPATCH");
    if(data.exposure=="HOLDOUT_SEALED"||data.first_day<integer(f.at("development_first_day"))||data.last_day>integer(f.at("development_last_day"))) fail("HOLDOUT_ACCESS_DENIED");
    const auto h0=integer(f.at("holdout_first_day")),h1=integer(f.at("holdout_last_day"));
    if(data.first_day<=h1&&data.last_day>=h0) fail("HOLDOUT_OVERLAP_DENIED");
}
std::string consume_holdout_grant(const std::filesystem::path& policy,const std::string& policy_sha,const std::filesystem::path& grant,const std::string& grant_sha,const std::filesystem::path& store) {
    const auto p=vault_policy(policy,policy_sha);
    if(p.at("exposure")!="HOLDOUT_SEALED")fail("HOLDOUT_GRANT_REQUIRES_SEALED_POLICY");
    const auto g=read_fields(grant,"QROS_HOLDOUT_GRANT_V1",grant_sha);
    exact_keys(g,{"policy_sha256","data_sha256","candidate_sha256","authorization_id","action","expires_unix_seconds"});
    if(g.at("policy_sha256")!=policy_sha||g.at("data_sha256")!=p.at("data_sha256")||g.at("authorization_id")!=p.at("authorization_id")||
       !hash_valid(g.at("candidate_sha256"))||g.at("action")!="FIXED_CANDIDATE_HOLDOUT") fail("HOLDOUT_GRANT_BINDING");
    const auto now=std::chrono::duration_cast<std::chrono::seconds>(std::chrono::system_clock::now().time_since_epoch()).count();
    if(integer(g.at("expires_unix_seconds"))<now) fail("HOLDOUT_GRANT_EXPIRED");
    std::filesystem::create_directories(store/"control");
    const auto lock_path=store/"control/VAULT_LOCK";
    if(std::filesystem::is_symlink(std::filesystem::symlink_status(lock_path))) fail("VAULT_LOCK_SYMLINK");
    const int fd=::open(lock_path.c_str(),O_RDWR|O_CREAT|O_NOFOLLOW|O_CLOEXEC,0600);
    if(fd<0) fail("VAULT_LOCK_OPEN");
    if(::flock(fd,LOCK_EX|LOCK_NB)!=0){::close(fd);fail("VAULT_ALREADY_OWNED");}
    try {
        const auto receipt_path=store/"control"/("consumed-"+policy_sha+".receipt");
        if(std::filesystem::exists(receipt_path)) fail("HOLDOUT_CAPABILITY_ALREADY_CONSUMED");
        const auto receipt=fields_text("QROS_HOLDOUT_CONSUMPTION_V1",{{"policy_sha256",policy_sha},{"grant_sha256",grant_sha},
            {"candidate_sha256",g.at("candidate_sha256")},{"data_sha256",g.at("data_sha256")},{"authorization_id",g.at("authorization_id")},
            {"status","CAPABILITY_CONSUMED"},{"economic_data_opened","0"},{"next_action","SEPARATE_FIXED_CANDIDATE_VALIDATION_REQUIRED"}});
        atomic_write_text(receipt_path,receipt);
        ::flock(fd,LOCK_UN);::close(fd);return receipt;
    } catch(...) {::flock(fd,LOCK_UN);::close(fd);throw;}
}
} // namespace qros::pipeline
