#include "qros/pipeline.hpp"
#include "qros/sha256.hpp"
#include <array>
#include <cerrno>
#include <fcntl.h>
#include <limits>
#include <sys/file.h>
#include <sys/random.h>
#include <sys/stat.h>
#include <unistd.h>

namespace qros::pipeline {
namespace {
const std::string genesis(64,'0');
std::string nonce();
void check_directory(const std::filesystem::path& path) {
    const auto absolute=std::filesystem::absolute(path).lexically_normal();
    std::filesystem::path current;
    for(const auto& component:absolute) {
        current/=component;
        if(std::filesystem::is_symlink(std::filesystem::symlink_status(current))) fail("STORE_SYMLINK_FORBIDDEN");
    }
    if(!std::filesystem::is_directory(path)) fail("STORE_DIRECTORY_REQUIRED");
}
void control_replace(const std::filesystem::path& path,const std::string& text) {
    check_directory(path.parent_path());
    if(std::filesystem::exists(path)) require_regular_path(path);
    auto temp=path;temp+=".pending."+std::to_string(::getpid())+"."+nonce();
    const int fd=::open(temp.c_str(),O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW|O_CLOEXEC,0600);
    if(fd<0) fail("CONTROL_TEMP_CONFLICT");
    std::size_t at=0;
    while(at<text.size()) {
        ssize_t n;do{n=::write(fd,text.data()+at,text.size()-at);}while(n<0&&errno==EINTR);
        if(n<=0){::close(fd);::unlink(temp.c_str());fail("CONTROL_WRITE_FAILED");}
        at+=static_cast<std::size_t>(n);
    }
    if(::fsync(fd)!=0){::close(fd);::unlink(temp.c_str());fail("CONTROL_FSYNC_FAILED");}
    if(::close(fd)!=0){::unlink(temp.c_str());fail("CONTROL_CLOSE_FAILED");}
    if(::rename(temp.c_str(),path.c_str())!=0){::unlink(temp.c_str());fail("CONTROL_RENAME_FAILED");}
    const int d=::open(path.parent_path().c_str(),O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC);
    if(d<0)fail("CONTROL_DIRECTORY_OPEN_FAILED");
    const int result=::fsync(d);::close(d);if(result!=0)fail("CONTROL_DIRECTORY_FSYNC_FAILED");
}
std::string nonce() {
    std::array<unsigned char,32> bytes{};std::size_t done=0;
    while(done<bytes.size()) {
        const auto n=::getrandom(bytes.data()+done,bytes.size()-done,0);
        if(n<0&&errno==EINTR)continue;
        if(n<=0)fail("OWNER_NONCE_UNAVAILABLE");
        done+=static_cast<std::size_t>(n);
    }
    Sha256Builder h;h.update(bytes.data(),bytes.size());return h.finish();
}
std::filesystem::path commit_path(const std::filesystem::path& root,u64 sequence) {
    return root/"control"/("commit-"+std::to_string(sequence)+".receipt");
}
Fields read_head(const std::filesystem::path& root) {
    const auto f=read_fields(root/"control/HEAD","QROS_RESULT_HEAD_V1");
    exact_keys(f,{"seq","end","head_sha256"});
    if(!hash_valid(f.at("head_sha256")))fail("HEAD_HASH_FORMAT");
    return f;
}
void validate_content(const std::string& text,u64 start,u64 end) {
    if(start>=end||end-start>100000||text.size()>512U*1024U*1024U)fail("CHUNK_RANGE_OR_SIZE");
    const auto prefix="QROS_RESULT_CHUNK_V1\nstart="+std::to_string(start)+"\nend="+std::to_string(end)+"\n";
    if(!text.starts_with(prefix))fail("CHUNK_RANGE_HEADER_MISMATCH");
    // Every raw birth has exactly one outcome record, including aliases/exclusions.
    std::size_t at=prefix.size();u64 expected=start,trade_count=0,declared_count=0,data_count=0;
    std::string active_id,active_status,ledger=ledger_header();u64 active_birth=0;
    const auto verify_count=[&]{if(!active_id.empty()&&trade_count!=declared_count)fail("CHUNK_TRADE_COUNT_MISMATCH");};
    while(at<text.size()) {
        const auto newline=text.find('\n',at);if(newline==std::string::npos)fail("CHUNK_UNTERMINATED_LINE");
        const auto line=text.substr(at,newline-at);
        if(line.starts_with("BIRTH,")) {
            verify_count();
            const auto parts=split(line,',');
            if(parts.size()!=5||natural(parts[1])!=expected||!hash_valid(parts[2])||
               (parts[3]!="EXECUTED"&&parts[3]!="ALIAS"&&parts[3]!="EXCLUDED"&&parts[3]!="UNRESOLVED"))fail("CHUNK_BIRTH_SCHEMA");
            active_id=parts[2];active_status=parts[3];active_birth=expected;trade_count=0;declared_count=0;
            if(active_status=="EXECUTED"||active_status=="UNRESOLVED")declared_count=natural(parts[4]);
            else if(active_status=="ALIAS"&&natural(parts[4])>=expected)fail("CHUNK_ALIAS_NOT_PRIOR_BIRTH");
            else if(active_status=="EXCLUDED"&&!identifier(parts[4]))fail("CHUNK_EXCLUSION_FORMAT");
            ++expected;
        } else if(line.starts_with("TRADE,")) {
            const auto parts=split(line,',');
            if(parts.size()!=20||active_id.empty()||(active_status!="EXECUTED"&&active_status!="UNRESOLVED")||parts[1]!=active_id||natural(parts[2])!=active_birth)fail("CHUNK_TRADE_SCOPE");
            ++trade_count;ledger+=line.substr(6)+"\n";
        } else if(line.starts_with("DATA,")) {
            const auto parts=split(line,',');
            if(parts.size()!=2||!hash_valid(parts[1])||++data_count!=1||expected!=start)fail("CHUNK_DATA_BINDING");
        } else fail("CHUNK_UNKNOWN_RECORD");
        at=newline+1;
    }
    verify_count();
    if(expected!=end||data_count!=1)fail("CHUNK_BIRTH_COVERAGE_OR_DATA_GAP");
    (void)parse_ledger(ledger);
}
}
ResultStore::ResultStore(std::filesystem::path root,std::string scope,std::string entrypoint,std::string binding)
    :root_(std::move(root)),scope_(std::move(scope)),entrypoint_(std::move(entrypoint)),binding_(std::move(binding)) {
    if(!identifier(scope_)||!hash_valid(entrypoint_)||!hash_valid(binding_))fail("STORE_BINDING_FORMAT");
    std::filesystem::create_directories(root_);check_directory(root_);
    for(const auto* subdir:{"control","chunks","final"}){std::filesystem::create_directories(root_/subdir);check_directory(root_/subdir);}
    lock_fd_=::open((root_/"control/LOCK").c_str(),O_RDWR|O_CREAT|O_NOFOLLOW|O_CLOEXEC,0600);
    if(lock_fd_<0)fail("STORE_LOCK_OPEN_FAILED");
    if(::flock(lock_fd_,LOCK_EX|LOCK_NB)!=0){::close(lock_fd_);lock_fd_=-1;fail("SCOPE_ALREADY_OWNED");}
    try {
        const auto meta=fields_text("QROS_RESULT_SCOPE_V1",{{"scope",scope_},{"entrypoint_sha256",entrypoint_},{"binding_sha256",binding_}});
        if(std::filesystem::exists(root_/"control/SCOPE")&&bounded_text(root_/"control/SCOPE")!=meta)fail("STORE_INPUT_OR_ENTRYPOINT_CHANGED");
        atomic_write_text(root_/"control/SCOPE",meta);
        fence_=1;
        if(std::filesystem::exists(root_/"control/FENCE")) {
            const auto f=read_fields(root_/"control/FENCE","QROS_FENCE_V1");
            exact_keys(f,{"fence"});const auto old=natural(f.at("fence"));
            if(old==std::numeric_limits<u64>::max())fail("FENCE_OVERFLOW");
            fence_=old+1;
        }
        control_replace(root_/"control/FENCE",fields_text("QROS_FENCE_V1",{{"fence",std::to_string(fence_)}}));
        owner_=std::to_string(::getpid());nonce_=nonce();
        if(!std::filesystem::exists(root_/"control/HEAD"))control_replace(root_/"control/HEAD",fields_text("QROS_RESULT_HEAD_V1",{{"seq","0"},{"end","0"},{"head_sha256",genesis}}));
        const auto h=read_head(root_);sequence_=natural(h.at("seq"));committed_end_=natural(h.at("end"));head_=h.at("head_sha256");
        if(sequence_>10000000)fail("RESULT_SEQUENCE_BUDGET");
        u64 end=0;std::string parent=genesis;
        const auto validate_commit=[&](u64 seq)->Fields {
            const auto cp=commit_path(root_,seq);const auto raw=bounded_text(cp);
            const auto f=parse_fields(raw,"QROS_CHUNK_COMMIT_V1");
            exact_keys(f,{"seq","start","end","previous_sha256","scope","binding_sha256","entrypoint_sha256","chunk","chunk_sha256"});
            if(natural(f.at("seq"))!=seq||natural(f.at("start"))!=end||f.at("previous_sha256")!=parent||f.at("scope")!=scope_||f.at("binding_sha256")!=binding_||f.at("entrypoint_sha256")!=entrypoint_)fail("RESULT_CHAIN_BINDING");
            if(f.at("chunk")!=std::to_string(end)+"-"+f.at("end")+".chunk")fail("RESULT_NONCANONICAL_CHUNK_PATH");
            const auto content=bounded_text(safe_relative(root_/"chunks",f.at("chunk")),512U*1024U*1024U);
            if(sha256_text(content)!=f.at("chunk_sha256"))fail("RESULT_CHUNK_CORRUPTED");
            validate_content(content,end,natural(f.at("end")));
            end=natural(f.at("end"));parent=sha256_text(raw);return f;
        };
        for(u64 seq=1;seq<=sequence_;++seq)(void)validate_commit(seq);
        if(end!=committed_end_||parent!=head_)fail("HEAD_CHAIN_MISMATCH");
        // Adopt an already durable commit after a crash before HEAD replacement.
        // Read only the exact next sequence; no latest-file or glob resolution.
        if(std::filesystem::exists(commit_path(root_,sequence_+1))) {
            (void)validate_commit(sequence_+1);++sequence_;committed_end_=end;head_=parent;
            control_replace(root_/"control/HEAD",fields_text("QROS_RESULT_HEAD_V1",{{"seq",std::to_string(sequence_)},{"end",std::to_string(end)},{"head_sha256",parent}}));
        }
        const auto started=fields_text("QROS_DISPATCH_STARTED_V1",{{"scope",scope_},{"owner",owner_},{"nonce",nonce_},{"fence",std::to_string(fence_)},
            {"entrypoint_sha256",entrypoint_},{"binding_sha256",binding_},{"head_sha256",head_},{"queue_seq",std::to_string(sequence_)},
            {"next_birth",std::to_string(committed_end_)},{"action","MINE_DECLARED_BIRTH_RANGE"},{"lease","KERNEL_FLOCK_SINGLE_HOST"}});
        atomic_write_text(root_/"control"/("STARTED-"+std::to_string(fence_)+".receipt"),started);
    } catch(...) {::flock(lock_fd_,LOCK_UN);::close(lock_fd_);lock_fd_=-1;throw;}
}
ResultStore::~ResultStore(){if(lock_fd_>=0){::flock(lock_fd_,LOCK_UN);::close(lock_fd_);}}
void ResultStore::commit(u64 start,u64 end,const std::string& content,const std::string& expected_head) {
    if(lock_fd_<0||expected_head!=head_||start!=committed_end_)fail("STALE_WRITER_CAS");
    const auto h=read_head(root_),f=read_fields(root_/"control/FENCE","QROS_FENCE_V1");
    if(h.at("head_sha256")!=head_||natural(h.at("seq"))!=sequence_||natural(h.at("end"))!=start||natural(f.at("fence"))!=fence_)fail("STALE_FENCE_OR_HEAD");
    validate_content(content,start,end);
    const auto name=std::to_string(start)+"-"+std::to_string(end)+".chunk";
    atomic_write_text(root_/"chunks"/name,content);
    const auto receipt=fields_text("QROS_CHUNK_COMMIT_V1",{{"seq",std::to_string(sequence_+1)},{"start",std::to_string(start)},{"end",std::to_string(end)},
        {"previous_sha256",head_},{"scope",scope_},{"binding_sha256",binding_},{"entrypoint_sha256",entrypoint_},{"chunk",name},{"chunk_sha256",sha256_text(content)}});
    atomic_write_text(commit_path(root_,sequence_+1),receipt);
    const auto new_head=sha256_text(receipt);
    control_replace(root_/"control/HEAD",fields_text("QROS_RESULT_HEAD_V1",{{"seq",std::to_string(sequence_+1)},{"end",std::to_string(end)},{"head_sha256",new_head}}));
    head_=new_head;committed_end_=end;++sequence_;
}
} // namespace qros::pipeline
