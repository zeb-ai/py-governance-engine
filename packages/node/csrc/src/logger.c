#include "../include/logger.h"
#include <stdarg.h>
#include <stdlib.h>
#include <time.h>

static const char *level_strings[] = {"DEBUG", "INFO", "WARN", "ERROR"};

Logger *logger_init(LogLevel level, const char *path) {
  Logger *logger = malloc(sizeof(Logger));
  if (!logger)
    return nullptr;

  logger->level = level;
  logger->file = nullptr;

  if (path) {
    logger->file = fopen(path, "w");
    if (!logger->file) {
      free(logger);
      return nullptr;
    }
  }

  return logger;
}

void logger_log(Logger *logger, LogLevel level, const char *fmt, ...) {
  if (!logger || level < logger->level)
    return;

  time_t now = time(nullptr);
  struct tm *tm = localtime(&now);
  char timestamp[32];
  strftime(timestamp, sizeof(timestamp), "%Y-%m-%d %H:%M:%S", tm);

  va_list args;

  if (logger->file) {
    fprintf(logger->file, "[%s] [%s] ", timestamp, level_strings[level]);
    va_start(args, fmt);
    vfprintf(logger->file, fmt, args);
    va_end(args);
    fprintf(logger->file, "\n");
    fflush(logger->file);
  }

  if (level >= LOG_WARN) {
    fprintf(stderr, "[z-grc] [%s] ", level_strings[level]);
    va_start(args, fmt);
    vfprintf(stderr, fmt, args);
    va_end(args);
    fprintf(stderr, "\n");
  }
}

void logger_free(Logger *logger) {
  if (!logger)
    return;
  if (logger->file)
    fclose(logger->file);
  free(logger);
}
