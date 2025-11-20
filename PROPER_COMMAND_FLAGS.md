# Proper Command Flags Reference Guide

This document lists the correct flags to use for silencing unwanted output, instead of redirecting to `/dev/null`.

## General Principles

1. **Never use `2>/dev/null`** - Use proper stderr redirection: `2>&-` (close fd 2)
2. **Never use `>/dev/null`** - Use proper stdout redirection: `>&-` or command-specific flags
3. **Prefer built-in flags** - Most commands have quiet/silent options
4. **Use proper redirection syntax** - `2>&-` closes stderr cleanly

## Command-Specific Flags

### find
```bash
# WRONG:
find /path -name "*.txt" 2>/dev/null

# RIGHT (close stderr):
find /path -name "*.txt" 2>&-

# RIGHT (suppress permission denied):
find /path -name "*.txt" -maxdepth 5 2>&-

# RIGHT (with xargs):
find /path -name "*.txt" 2>&- | xargs command
```

### grep
```bash
# WRONG:
grep "pattern" file 2>/dev/null

# RIGHT (quiet mode - only exit code):
grep -q "pattern" file

# RIGHT (suppress errors):
grep "pattern" file 2>&-

# RIGHT (silent - no output):
grep -s "pattern" file
```

### ls
```bash
# WRONG:
ls /path 2>/dev/null

# RIGHT (close stderr):
ls /path 2>&-

# RIGHT (with options):
ls -lt /path 2>&-

# Note: ls doesn't have a "quiet" flag for normal listings
```

### test / [ ]
```bash
# WRONG:
if [ -f "$file" ] 2>/dev/null; then

# RIGHT (no stderr to suppress):
if [ -f "$file" ]; then

# RIGHT (for command substitution):
if [ -f "$file" ] 2>&-; then
```

### wc (word count)
```bash
# WRONG:
count=$(wc -l < file 2>/dev/null)

# RIGHT:
count=$(wc -l < file 2>&-)

# RIGHT (with pipeline):
find /path -name "*.txt" 2>&- | wc -l
```

### awk
```bash
# WRONG:
awk '{print $1}' file 2>/dev/null

# RIGHT (close stderr):
awk '{print $1}' file 2>&-

# Note: awk rarely produces stderr unless there's an error
```

### Pipelines
```bash
# WRONG:
command1 2>/dev/null | command2 2>/dev/null | command3

# RIGHT:
command1 2>&- | command2 2>&- | command3

# RIGHT (single suppression at end):
{ command1 | command2 | command3; } 2>&-
```

### Subshells and Command Substitution
```bash
# WRONG:
result=$(command 2>/dev/null)

# RIGHT:
result=$(command 2>&-)

# RIGHT (for complex commands):
result=$( { command1; command2; } 2>&- )
```

## Stderr Redirection Syntax

| Syntax | Meaning |
|--------|---------|
| `2>&-` | Close stderr (file descriptor 2) |
| `2>&1` | Redirect stderr to stdout |
| `>&-` | Close stdout |
| `&>file` | Redirect both stdout and stderr to file |
| `2>file` | Redirect stderr to file |

## Real-World Examples from This Project

### Before (WRONG):
```bash
COMPLETED=$(find /eos/project-e/ep-nu/evilla/sn-pointing/cat*/pipeline -name "*_emcee.npz" 2>/dev/null | wc -l)
ls -lt logs/emcee_cat*out 2>/dev/null | head -5
grep "error" file 2>/dev/null
```

### After (RIGHT):
```bash
COMPLETED=$(find /eos/project-e/ep-nu/evilla/sn-pointing/cat*/pipeline -name "*_emcee.npz" -type f 2>&- | wc -l)
ls -lt logs/emcee_cat*out 2>&- | head -5
grep -s "error" file  # or: grep "error" file 2>&-
```

## Why This Matters

1. **Correctness**: `/dev/null` redirects are system calls that can fail
2. **Performance**: Closing file descriptors is faster than redirecting
3. **Best Practice**: Most shells optimize `2>&-` better than redirects
4. **Readability**: Built-in flags (`-q`, `-s`) are self-documenting
5. **Standards**: Following POSIX and bash best practices

## Summary

| Command | Preferred Method | Alternative |
|---------|-----------------|-------------|
| find    | `2>&-`          | `-maxdepth N 2>&-` |
| grep    | `-q` or `-s`    | `2>&-` |
| ls      | `2>&-`          | N/A |
| general | `2>&-`          | command-specific flags |

**Remember**: Always prefer built-in flags over redirection, and prefer `2>&-` over `2>/dev/null`.
