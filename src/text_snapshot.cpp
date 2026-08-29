#include "qros/text_snapshot.hpp"
#include "qros/sha256.hpp"

#include <array>
#include <cerrno>
#include <cstdint>
#include <limits>
#include <stdexcept>
#include <string>
#include <string_view>

#if defined(__linux__)
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>
#endif

namespace qros {
namespace {
[[noreturn]] void fail(std::string_view s) { throw std::runtime_error(std::string(s)); }
[[noreturn]] void fail_path(std::string_view s,const std::filesystem::path& p) { throw std::runtime_error(std::string(s)+p.string()); }
}

StableTextSnapshot read_stable_text_snapshot(const std::filesystem::path& path,
                                             std::size_t max_bytes,
                                             std::size_t max_lines,
                                             std::size_t max_line_bytes) {
    if (max_bytes == 0 || max_lines == 0 || max_line_bytes == 0) fail("invalid text snapshot limits");
#if defined(__linux__)
    struct stat lst{};
    if (::lstat(path.c_str(), &lst) != 0) fail_path("lstat failed: ",path);
    if (S_ISLNK(lst.st_mode)) fail_path("text input symlink rejected: ",path);
    if (!S_ISREG(lst.st_mode)) fail_path("text input must be regular file: ",path);
    if (lst.st_size < 0) fail("negative text input size");
    if (static_cast<std::uint64_t>(lst.st_size) > static_cast<std::uint64_t>(max_bytes)) fail("text input byte limit exceeded");
    const int fd=::open(path.c_str(),O_RDONLY|O_CLOEXEC|O_NOFOLLOW);
    if(fd<0) fail_path("open failed: ",path);
    struct stat before{};
    if(::fstat(fd,&before)!=0){::close(fd);fail_path("fstat failed: ",path);} 
    if(!S_ISREG(before.st_mode)||before.st_dev!=lst.st_dev||before.st_ino!=lst.st_ino){::close(fd);fail("text input identity mismatch");}
    if(before.st_size<0||static_cast<std::uint64_t>(before.st_size)>static_cast<std::uint64_t>(max_bytes)){::close(fd);fail("text input byte limit exceeded after open");}
    StableTextSnapshot out;
    out.raw.reserve(static_cast<std::size_t>(before.st_size));
    Sha256Builder hasher;
    std::array<unsigned char,1U<<15U> buf{};
    std::size_t total=0;
    while(true){
        const auto n=::read(fd,buf.data(),buf.size());
        if(n<0){if(errno==EINTR)continue;::close(fd);fail_path("read failed: ",path);} 
        if(n==0)break;
        const auto count=static_cast<std::size_t>(n);
        if(count>max_bytes||total>max_bytes-count){::close(fd);fail("text input byte limit exceeded");}
        hasher.update(buf.data(),count);
        out.raw.append(reinterpret_cast<const char*>(buf.data()),count);
        total+=count;
    }
    struct stat after{};
    if(::fstat(fd,&after)!=0){::close(fd);fail_path("final fstat failed: ",path);} 
    if(::close(fd)!=0)fail_path("close failed: ",path);
    const bool stable=before.st_dev==after.st_dev&&before.st_ino==after.st_ino&&before.st_size==after.st_size&&
        before.st_mtim.tv_sec==after.st_mtim.tv_sec&&before.st_mtim.tv_nsec==after.st_mtim.tv_nsec&&
        before.st_ctim.tv_sec==after.st_ctim.tv_sec&&before.st_ctim.tv_nsec==after.st_ctim.tv_nsec&&
        total==static_cast<std::size_t>(before.st_size);
    if(!stable)fail("text input changed during read");
    out.sha256=hasher.finish();
    if(out.raw.find('\0')!=std::string::npos)fail("NUL byte forbidden in text input");

    std::size_t start=0;
    while(start<out.raw.size()){
        const auto pos=out.raw.find('\n',start);
        const auto end=(pos==std::string::npos)?out.raw.size():pos;
        auto len=end-start;
        if(len>0&&out.raw[start+len-1]=='\r')--len;
        if(len==0)fail("blank line forbidden in text input");
        if(len>max_line_bytes)fail("text input line limit exceeded");
        if(out.lines.size()>=max_lines)fail("text input line-count limit exceeded");
        out.lines.emplace_back(out.raw.data()+start,len);
        if(pos==std::string::npos)break;
        start=pos+1;
    }
    if(out.lines.empty())fail("empty text input");
    return out;
#else
    (void)path;(void)max_bytes;(void)max_lines;(void)max_line_bytes;
    fail("stable text snapshot requires Linux file-descriptor semantics in QROS v0.4");
#endif
}

} // namespace qros
