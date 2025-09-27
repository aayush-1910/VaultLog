# VaultLog

VaultLog is a journaling project I’m building in Python. The idea is simple: keep everything offline and secure so entries stay private. Each log is encrypted with AES before it’s saved, and you can add entries through either a basic CLI or a small GUI. Every entry is timestamped, and there’s an in-memory search to go through logs without exposing the raw files.

## Features
- AES encryption for all entries  
- CLI and GUI support for writing logs  
- Automatic timestamps  
- In-memory search  
- Works fully offline  

## Purpose
Most journaling tools store data in the cloud. VaultLog is meant for people who prefer to keep their thoughts and notes local, private, and under their control. It’s a simple start, but something I’ll keep improving as I learn.  

## Limitations
- Losing the password/key means losing access to the data  
- In-memory search may slow down with very large log sets  
- GUI is minimal for now

## Roadmap
- Better key handling  
- Encrypted database integration (SQLite)  
- Cleaner UI/UX  
- Import/export support  

## Status
Active development. First version is live and will continue to improve as I learn and grow.
