# SBF Styring

Dette projekt er et Python-baseret system til styring og synkronisering af data mellem kommunale fagsystemer: Dubu, Nexus, Momentum og Datafordeler.

## Funktionalitet
- Synkroniserer borgere og sagsbehandlere på tværs af systemer
- Henter og opdaterer data fra eksterne systemer via klientbiblioteker
- Bruger PostgreSQL til lagring af data

## Installation
1. Klon projektet
2. Installer afhængigheder med `uv sync`
3. Opret en PostgreSQL-database og opdater `.env` med din forbindelse

## Opsætning
- Konfigurer adgang til eksterne systemer i `.env`-filen
- Start applikationen med:
  ```bash
  uv run main.py
  ```

