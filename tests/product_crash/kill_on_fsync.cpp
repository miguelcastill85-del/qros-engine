#include <atomic>
#include <cerrno>
#include <csignal>
#include <cstdlib>
#include <dlfcn.h>
#include <unistd.h>
extern "C" int fsync(int fd){
 using Original=int(*)(int);
 static Original original=reinterpret_cast<Original>(dlsym(RTLD_NEXT,"fsync"));
 static std::atomic<int> count{0};
 if(original==nullptr){errno=ENOSYS;return -1;}
 const int result=original(fd);
 const int ordinal=++count;
 const auto raw=std::getenv("QROS_M2_KILL_AFTER_FSYNC");
 if(raw && result==0 && ordinal==std::atoi(raw)){
  const char marker[]="TEST_ONLY_FSYNC_CRASH_INJECTED\n";
  (void)::write(STDERR_FILENO,marker,sizeof(marker)-1);
  ::kill(::getpid(),SIGKILL);
 }
 return result;
}
