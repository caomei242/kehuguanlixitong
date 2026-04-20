#include <fcntl.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/types.h>
#include <unistd.h>

static const char *REPO_DIR = "/Users/gd/Desktop/主业--草莓客户管理系统";
static const char *SRC_DIR = "/Users/gd/Desktop/主业--草莓客户管理系统/src";
static const char *PYTHON_BIN = "/Applications/Xcode.app/Contents/Developer/usr/bin/python3";
static const char *LOG_PATH = "/tmp/strawberry-customer-launcher.log";

static void write_log(const char *fmt, ...) {
    FILE *fp = fopen(LOG_PATH, "a");
    if (!fp) {
        return;
    }
    va_list args;
    va_start(args, fmt);
    vfprintf(fp, fmt, args);
    va_end(args);
    fputc('\n', fp);
    fclose(fp);
}

static void activate_python_app(void) {
    system("osascript -e 'tell application \"Python\" to activate' >/dev/null 2>&1");
}

static void launch_python_app(void) {
    pid_t pid = fork();
    write_log("launch_python_app fork pid=%d", (int)pid);
    if (pid != 0) {
        return;
    }

    if (chdir(REPO_DIR) != 0) {
        write_log("child chdir failed");
        _exit(120);
    }

    setenv("PYTHONPATH", SRC_DIR, 1);
    setenv("QT_QPA_PLATFORM", "cocoa", 1);

    int log_fd = open(LOG_PATH, O_WRONLY | O_CREAT | O_APPEND, 0644);
    if (log_fd >= 0) {
        dup2(log_fd, STDOUT_FILENO);
        dup2(log_fd, STDERR_FILENO);
        close(log_fd);
    }

    int null_fd = open("/dev/null", O_RDONLY);
    if (null_fd >= 0) {
        dup2(null_fd, STDIN_FILENO);
        close(null_fd);
    }

    execl(
        PYTHON_BIN,
        "python3",
        "-m",
        "strawberry_customer_management.app",
        (char *)NULL
    );
    write_log("child execl failed");
    _exit(127);
}

int main(void) {
    int running = system("pgrep -f 'python.*strawberry_customer_management\\.app' >/dev/null 2>&1");
    write_log("main running_check=%d", running);
    if (running == 0) {
        activate_python_app();
        return 0;
    }

    launch_python_app();
    sleep(1);
    activate_python_app();
    return 0;
}
