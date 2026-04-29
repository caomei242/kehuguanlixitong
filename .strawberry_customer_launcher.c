#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/types.h>
#include <unistd.h>

static const char *REPO_DIR = "/Users/gd/Desktop/主业--草莓客户管理系统";
static const char *SRC_DIR = "/Users/gd/Desktop/主业--草莓客户管理系统/src";
static const char *PYTHON_BIN = "/Applications/Xcode.app/Contents/Developer/Library/Frameworks/Python3.framework/Versions/3.9/Resources/Python.app/Contents/MacOS/Python";
static const char *LOG_PATH = "/tmp/strawberry-customer-launcher.log";
static const char *PID_PATH = "/tmp/strawberry-customer-launcher.pid";

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

static void write_pid(pid_t pid) {
    FILE *fp = fopen(PID_PATH, "w");
    if (!fp) {
        return;
    }
    fprintf(fp, "%d\n", (int)pid);
    fclose(fp);
}

static pid_t read_pid(void) {
    FILE *fp = fopen(PID_PATH, "r");
    if (!fp) {
        return 0;
    }
    int pid = 0;
    if (fscanf(fp, "%d", &pid) != 1) {
        fclose(fp);
        return 0;
    }
    fclose(fp);
    return (pid_t)pid;
}

static int process_alive(pid_t pid) {
    if (pid <= 0) {
        return 0;
    }
    if (kill(pid, 0) == 0) {
        return 1;
    }
    return errno == EPERM;
}

static int activate_customer_window(void) {
    const char *command =
        "osascript >/dev/null 2>&1 <<'APPLESCRIPT'\n"
        "tell application \"System Events\"\n"
        "    repeat with proc in (every process whose name is \"Python\")\n"
        "        tell proc\n"
        "            try\n"
        "                if exists (first window whose title contains \"草莓客户管理系统\") then\n"
        "                    set frontmost to true\n"
        "                    perform action \"AXRaise\" of (first window whose title contains \"草莓客户管理系统\")\n"
        "                    return\n"
        "                end if\n"
        "            end try\n"
        "        end tell\n"
        "    end repeat\n"
        "    error number 4\n"
        "end tell\n"
        "APPLESCRIPT";
    return system(command);
}

static pid_t launch_python_app(void) {
    pid_t pid = fork();
    write_log("launch_python_app fork pid=%d", (int)pid);
    if (pid != 0) {
        if (pid > 0) {
            write_pid(pid);
        }
        return pid;
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
        "Python",
        "-m",
        "strawberry_customer_management.app",
        (char *)NULL
    );
    write_log("child execl failed");
    _exit(127);
}

int main(void) {
    pid_t pid = read_pid();
    if (process_alive(pid)) {
        int activated = activate_customer_window();
        write_log("main activate_existing pid=%d code=%d", (int)pid, activated);
        if (activated == 0) {
            return 0;
        }
    }

    pid = launch_python_app();
    sleep(2);
    int activated = activate_customer_window();
    write_log("main activate_after_launch pid=%d code=%d", (int)pid, activated);
    return 0;
}
