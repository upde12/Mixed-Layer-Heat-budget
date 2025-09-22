---
title: Paramiko SSH banner 리셋
date: 2025-09-22 17:35
category: remote_ops
tags: [ssh, paramiko, remote]
related:
  - scripts/log_error_note.py
---

## 상황 요약
- paramiko로 147.46.93.191:2222에 접속 시도 중 banner 협상 단계에서 연결이 끊김

## 에러 메시지
```
paramiko.ssh_exception.SSHException: Error reading SSH protocol banner[Errno 54] Connection reset by peer
```

## 원인 진단
- 서버가 Paramiko 기본 handshake를 거부하거나 방화벽이 비표준 클라이언트를 차단

## 해결 절차
1. sshpass+ssh 명령으로 접속 전환 (StrictHostKeyChecking=no) 후 작업 수행

## 예방 및 메모
- 후속 조치 및 참고 링크를 작성하세요.
