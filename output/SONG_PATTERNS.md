# NES Play-Song Patterns — ROM Patch Reference

113 games with identified `LDA #song_id; JSR play_song` patterns in the fixed bank.
Each can be ROM-patched for multi-song extraction.

## Method
Find the first `LDA #xx; JSR $yyyy` in the fixed bank (last 16KB of ROM).
Patch the byte after LDA to a different song number. Reboot. Capture.

## Top Games (Most Songs)

| Game | Songs | JSR Target | Mapper |
|------|-------|------------|--------|
| Castlevania | 21 | $C1A7 | 2 |
| Elevator Action | 20 | $F6DB | 0 |
| Rush'n Attack | 20 | $DFA8 | 2 |
| Super Pitfall | 19 | $FEAC | 4 |
| Ms. Pac-Man | 17 | $F2FF | 0 |
| Felix the Cat | 15 | $FF1A | 4 |
| BurgerTime | 14 | $C026 | 0 |
| Blades of Steel | 13 | $C3CB | 2 |
| Ninja Gaiden | 12 | $E254 | 1 |
| Little Nemo | 11 | $FC7F | 4 |
| Super Contra | 11 | $FE3E | 4 |
| Jackal | 11 | $C36B | 2 |
| Ghosts'n Goblins | 10 | $ED51 | 2 |
| Commando | 10 | $CE58 | 2 |
| Mega Man 1 | 9 | $C477 | 2 |
| Mega Man 3 | 9 | $F835 | 4 |
| Faxanadu | 9 | $D0E4 | 1 |
| Little Samson | 9 | $E72B | 4 |
| Blaster Master | 8 | $DECC | 2 |  
| Magic of Scheherazade | 8 | $E992 | 1 |
| Legend of Zelda | 7 | $FFAC | 1 |
| Metal Gear | 7 | $D4A4 | 2 |
| StarTropics | 7 | $E5D3 | 4 |
| Bionic Commando | 7 | $D6E2 | 1 |
| Journey to Silius | 6 | $C6ED | 1 |
| Mega Man 6 | 6 | $C5F6 | 4 |
| Batman | 6 | $C8C0 | 4 |
| Crystalis | 5 | $C418 | 4 |
| DuckTales | 5 | $FFDE | 2 |
| Double Dragon | 5 | $FEEE | 1 |
