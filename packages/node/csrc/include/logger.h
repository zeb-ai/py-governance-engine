#pragma once

#include <stdio.h>

typedef enum {
  LOG_DEBUG = 0,
  LOG_INFO = 1,
  LOG_WARN = 2,
  LOG_ERROR = 3,
} LogLevel;

typedef struct {
  FILE *file;
  LogLevel level;
} Logger;

Logger *logger_init(LogLevel level, const char *path);
void logger_log(Logger *logger, LogLevel level, const char *fmt, ...);
void logger_free(Logger *logger);
