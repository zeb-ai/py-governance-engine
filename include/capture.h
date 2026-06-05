//
// Created by Samrat on 04/06/26.
//

#pragma once

#ifdef _WIN32
#include <winsock2.h>
#include <ws2tcpip.h>
#else
#include <arpa/inet.h>
#include <netinet/in.h>
#include <sys/socket.h>
#endif

#include <stddef.h>

void interceptor_init(void);
void interceptor_destroy(void);

int _intercept_connect(int fd, const struct sockaddr *, socklen_t);
int _intercept_send(int fd, const void *, size_t, int);
int _intercept_recv(int fd, void *, size_t, int);

#define connect(fd, addr, len) _intercept_connect(fd, addr, len)
#define send(fd, buf, len, flags) _intercept_send(fd, buf, len, flags)
#define recv(fd, buf, len, flags) _intercept_recv(fd, buf, len, flags)
