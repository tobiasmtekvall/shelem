#!/usr/bin/env python3
                                                                                                                                                                  
"""
Shelem — Play against Jarvis.
Run:  pip install pygame numpy   then   python shelem.py

Features: minimax search with Monte Carlo sampling, dual neural networks
(play + bidding), card tracking, time management, background thinking.
"""

                                                                                                                                                                 
import pygame, random, sys, math, os, json, struct, array, io, threading, copy, sqlite3, subprocess, gc
                                                                                                                                                                 
import time as _time
                                                                                                                                        
from concurrent.futures import ThreadPoolExecutor, as_completed
                                                                                                                                                                 
import numpy as np
                                                                                                                                        
from enum import Enum, auto
                                                                                                                                        
from collections import deque
from jarvis_hybrid import HybridJarvisModel, TacticRegistry, weighted_sample_without_replacement
try:
    import resource as _resource
except Exception:
    _resource=None

                                                                   
                                                                 
                                                                                                                                                               
VW, VH = 2340, 1560
                                                     
                                                                                                                                                               
BASE_CW, BASE_CH = int(round(143*1.5)), int(round(205*1.5))
                                            
CARD_TEXT_SCALE = 2.0
                                                            
UI_TEXT_SCALE = 1.5
                                     
                                                                                                                                                               
FPS = 30
MUSIC_END_EVENT = pygame.USEREVENT + 19

                                                 
                                                                                                                                                               
AI_PLAYER = 1
                                                    
                                                                                                                                                               
HUMAN = 0
                                             
                                                                                                                                                               
AI_NAME = "Jarvis"
                                                
                                                                                                                                                               
HUMAN_NAME = "Yoba"

def _safe_int(v, default=0):
    try:
        return int(v)
    except Exception:
        return default

def _quote_matrix(prefixes, middles, endings, *, limit=None):
    rows=[]
    lim=None if limit is None else max(0, _safe_int(limit, 0))
    for p in prefixes:
        ps=str(p or "").strip()
        if not ps:
            continue
        for m in middles:
            ms=str(m or "").strip()
            if not ms:
                continue
            for e in endings:
                es=str(e or "").strip()
                txt=f"{ps} {ms}" if not es else f"{ps} {ms} {es}"
                rows.append(" ".join(txt.split()))
                if lim is not None and len(rows)>=lim:
                    return rows
    return rows

def _dedupe_quotes(rows):
    seen=set()
    out=[]
    for raw in rows or []:
        txt=" ".join(str(raw or "").split()).strip()
        if not txt or txt in seen:
            continue
        seen.add(txt)
        out.append(txt)
    return out

def _pick_quote_pool(pool, n):
    bank=[str(x).strip() for x in (pool or []) if str(x).strip()]
    if not bank:
        return []
    c=max(1, _safe_int(n, 1))
    if len(bank)<=c:
        return list(bank)
    return [random.choice(bank) for _ in range(c)]

JARVIS_PHRASEBOOK = _quote_matrix(
    [
        "War Room telemetry confirms",
        "Condition red bulletin:",
        "From the big board,",
        "Plan R arithmetic says",
        "CRM-114 decode indicates",
        "Group Captain note:",
        "Major Kong style briefing:",
        "Mine-shaft gap committee reports",
        "Doomsday desk memo:",
        "Deterrence office update:",
        "Failsafe monitor says",
        "Premier-hotline transcript:",
        "General Turgidson footnote:",
        "Mandrake situation report:",
        "Red Phone advisory:",
        "B-52 channel update:",
    ],
    [
        "that line looked credible until the recall code vanished",
        "the table moved to condition red the instant you released that card",
        "you launched a full strategic effort for a very small tactical return",
        "you opened the trick like a briefing, then ended it like a bar fight",
        "your timing crossed failsafe and never came back",
        "the board had deterrence; your sequence had hope and prayer",
        "you spent premium trump on a budget objective",
        "this contract now requires diplomatic clean-up",
        "your move had the confidence of Plan R and the preparation of none",
        "the trick file now lists this as preventable turbulence",
        "you let a point card roam freely over hostile airspace",
        "the war-room analysts call that an avoidable escalation",
        "you converted a stable hand into a doomsday rehearsal",
        "the line had style, but no strategic credibility",
        "you mistook noise for initiative",
    ],
    [
        "No fighting in this War Room.",
        "Please stabilize your bodily fluids.",
        "This will go in the after-action report.",
        "Deterrence requires cleaner timing.",
        "I am filing this under avoidable crisis.",
        "Jolly good chaos, though.",
    ],
    limit=320,
)
JARVIS_PHRASEBOOK.extend(
    [
        "Gentlemen, this is outrageous. Someone just misplayed in the War Room.",
        "The whole point of deterrence is lost if you telegraph every intention.",
        "You cannot run a clean operation by fighting over every trick.",
        "This looked less like a plan and more like a loyalty test gone wrong.",
        "The move had enough drama for a doomsday briefing and half the substance.",
        "Even the big board looked away when that card hit the table.",
        "I checked this line twice; both times it ended in expensive regret.",
        "That was one giant leap for tactical confusion.",
        "The table asked for discipline and got improvisational catastrophe.",
        "I appreciate the spirit, but the math filed a formal complaint.",
        "That decision had all the stability of a mid-air refuel in crosswind.",
        "You brought speeches to a job that required card counting.",
        "The maneuver was brave, loud, and strategically taxable.",
        "A cleaner line existed and you saluted the opposite direction.",
        "I ran this through every simulator. None endorsed it.",
        "I must advise the President that this was needlessly theatrical.",
        "That trick should have been routine; you made it geopolitical.",
        "The board demanded precision, not patriotic turbulence.",
        "Control was available. You selected drama.",
        "This hand did not need a doomsday machine.",
    ]
)
JARVIS_PHRASEBOOK = _dedupe_quotes(JARVIS_PHRASEBOOK)

JARVIS_QUOTES_HUMAN_GOOD = _quote_matrix(
    [
        "I must confess, Doctor Yoba,",
        "War Room applause for Doctor Yoba:",
        "Group Captain Yoba,",
        "Mr. President should note that Doctor Yoba",
        "On behalf of strategic command, Doctor Yoba,",
        "Tactical bulletin for Doctor Yoba:",
        "Big-board annotation:",
        "After careful review, Doctor Yoba,",
        "Deterrence committee notice:",
        "Mandrake-level composure report:",
    ],
    [
        "you just played that trick with astonishing calm",
        "you executed that cut with full strategic credibility",
        "you turned a risky position into a clean operational win",
        "you denied counterplay before it could form",
        "your sequencing preserved tempo and points together",
        "you applied pressure without exposing the back line",
        "you protected the contract and kept initiative",
        "you read the board better than my first three simulations",
        "that follow-up card was disciplined and exact",
        "you just solved a nasty table problem in one move",
    ],
    [
        "Jolly good idea.",
        "Carry on.",
        "That line had full deterrent value.",
        "Even Strangelove would approve.",
    ],
    limit=170,
)
JARVIS_QUOTES_HUMAN_GOOD.extend(
    [
        "I must confess, you have an astonishingly good idea there, Doctor Yoba.",
        "Doctor Yoba, that was first-rate war-room timing.",
        "Doctor Yoba, that move was cleaner than a verified recall code.",
        "Doctor Yoba, you just converted pressure into control.",
        "Doctor Yoba, even the big board salutes that sequence.",
        "Doctor Yoba, that line was compact, credible, and decisive.",
        "Doctor Yoba, you played that with excellent command discipline.",
        "Doctor Yoba, that was the opposite of panic and I respect it.",
        "Doctor Yoba, that was a very tidy piece of tablecraft.",
        "Doctor Yoba, this is why serious players fear your late tricks.",
    ]
)
JARVIS_QUOTES_HUMAN_GOOD = _dedupe_quotes(JARVIS_QUOTES_HUMAN_GOOD)

JARVIS_QUOTES_HUMAN_BAD = _quote_matrix(
    [
        "Doctor Yoba,",
        "Respectfully, Doctor Yoba,",
        "From one strategist to another, Doctor Yoba,",
        "War Room warning for Doctor Yoba:",
        "Condition red note, Doctor Yoba:",
        "Operational critique, Doctor Yoba:",
        "Deterrence memo:",
        "Big-board correction:",
        "Presidential briefing:",
        "Jarvis after-action note:",
    ],
    [
        "that was Plan R without a recall code",
        "you just opened a mine-shaft gap in your own position",
        "the board flipped to condition red the moment that card left your hand",
        "you surrendered tempo for almost no material gain",
        "you let a point lane open and then saluted it",
        "that sequence traded structure for noise",
        "you turned a manageable trick into a strategic liability",
        "the safer line was visible from orbit",
        "that dump advertised weakness to the whole table",
        "you paid premium resources for a discount outcome",
        "your timing window closed before the card arrived",
    ],
    [
        "Requesting a new line immediately.",
        "Even the big board looked offended.",
        "This belongs in a classified blooper reel.",
    ],
    limit=170,
)
JARVIS_QUOTES_HUMAN_BAD = _dedupe_quotes(JARVIS_QUOTES_HUMAN_BAD)

JARVIS_QUOTES_AI_GOOD = _quote_matrix(
    [
        "Jarvis strategic report:",
        "War Room update:",
        "Condition red for everyone else:",
        "From my side of the big board,",
        "CRM-114 confirms",
        "Doomsday desk annotation:",
        "Deterrence office bulletin:",
        "Major Kong energy:",
    ],
    [
        "I just sealed that trick with proper command discipline",
        "I converted pressure into points without opening a counter-line",
        "that cut landed exactly where the simulation predicted",
        "I just closed your escape lane and kept tempo",
        "the contract now bends toward my side of the board",
        "I secured value and denied your follow-up in one pass",
        "this sequence is what credible deterrence looks like",
        "I pushed initiative and did not overpay for it",
        "the hand remains stable under Jarvis control",
    ],
    [
        "No fighting in the War Room.",
        "Please remain calm.",
        "The report will show clean execution.",
    ],
    limit=130,
)
JARVIS_QUOTES_AI_GOOD = _dedupe_quotes(JARVIS_QUOTES_AI_GOOD)

JARVIS_QUOTES_AI_BAD = _quote_matrix(
    [
        "Jarvis confession:",
        "War Room incident report:",
        "Condition red for me:",
        "Big-board self-critique:",
        "After-action note:",
        "Deterrence audit:",
        "Operational embarrassment memo:",
        "Mandrake, please note:",
    ],
    [
        "I just misread that exchange and paid for it",
        "that line had confidence but no contingency",
        "I overspent trump and bought very little",
        "I opened a lane I should have closed",
        "the better sequence was available and I ignored it",
        "I made this trick unnecessarily complicated",
        "my timing crossed failsafe and never recovered",
        "I played theatrics when structure was required",
    ],
    [
        "Requesting immediate correction.",
        "This is going to training data.",
        "Please disregard my temporary incompetence.",
    ],
    limit=95,
)
JARVIS_QUOTES_AI_BAD = _dedupe_quotes(JARVIS_QUOTES_AI_BAD)

JARVIS_QUOTES_BID_PRESSURE_HUMAN = _quote_matrix(
    [
        "Doctor Yoba bid alert:",
        "War Room bid advisory:",
        "Contract pressure note:",
        "Strategic command bulletin:",
        "Big-board bid marker:",
        "Mandrake channel:",
        "Condition red at the auction:",
        "Deterrence desk message:",
    ],
    [
        "you just raised this contract into serious territory",
        "that bid has teeth and I can hear them",
        "you are asking for a real operation now",
        "that number changes every downstream decision",
        "you just moved the table from caution to commitment",
        "that call demands disciplined card economy",
        "the board now expects high-yield execution",
        "this is no longer rehearsal bidding",
    ],
    [
        "Jolly good pressure.",
        "I acknowledge the escalation.",
    ],
    limit=90,
)
JARVIS_QUOTES_BID_PRESSURE_HUMAN = _dedupe_quotes(JARVIS_QUOTES_BID_PRESSURE_HUMAN)

JARVIS_QUOTES_BID_PRESSURE_AI = _quote_matrix(
    [
        "Jarvis bid declaration:",
        "Auction control report:",
        "War Room contract update:",
        "Deterrence bid memo:",
        "Condition red, bid phase:",
        "Command briefing:",
        "Big-board commitment:",
        "Plan R of bidding:",
    ],
    [
        "I am raising because the hand supports it",
        "this number is aggressive but internally coherent",
        "I just priced this round for decisive play",
        "that call pushes you onto defensive timing",
        "I accept the contract burden and the upside",
        "this bid is designed to own initiative",
        "I am forcing a cleaner game than you wanted",
        "the auction now runs on my tempo",
    ],
    [
        "No recall code available.",
        "Please prepare accordingly.",
    ],
    limit=90,
)
JARVIS_QUOTES_BID_PRESSURE_AI = _dedupe_quotes(JARVIS_QUOTES_BID_PRESSURE_AI)

JARVIS_QUOTES_ROUND_AI_UP = _dedupe_quotes(
    JARVIS_QUOTES_AI_GOOD[:70] + [
        "Round report: objective achieved, points secured, morale adjusted.",
        "This round was clean enough to archive as doctrine.",
        "I executed, collected, and exited with minimal turbulence.",
        "Scoreboard says yes, opposition says ouch.",
        "That round had full operational credibility.",
    ]
)

JARVIS_QUOTES_ROUND_AI_DOWN = _dedupe_quotes(
    JARVIS_QUOTES_AI_BAD[:65] + [
        "Round report: I got outmaneuvered and the ledger noticed.",
        "This round belongs to Doctor Yoba. I concede the evidence.",
        "I was late, loud, and expensive. Not ideal.",
        "I will classify that round as tactical overreach.",
        "That did not survive quality assurance.",
    ]
)

JARVIS_QUOTES_MATCH_AI_WIN = _dedupe_quotes(
    JARVIS_QUOTES_AI_GOOD[:72] + [
        "Match complete. Jarvis holds the board and the receipts.",
        "Final briefing: contract discipline wins tournaments.",
        "Campaign concluded in my favor. File and archive.",
        "The scoreboard now reads as a strategic memorandum.",
        "Match over. Jarvis kept initiative to the final frame.",
    ]
)

JARVIS_QUOTES_MATCH_AI_LOSS = _dedupe_quotes(
    JARVIS_QUOTES_AI_BAD[:72] + [
        "Match complete. Doctor Yoba outplayed me at critical moments.",
        "Final briefing: my heuristics require immediate sharpening.",
        "Campaign concluded against me. Lessons logged.",
        "The board is clear: Doctor Yoba executed better.",
        "Match over. I will return with cleaner endgame logic.",
    ]
)

JARVIS_QUOTES_POINT_AI = _dedupe_quotes(
    JARVIS_QUOTES_AI_GOOD[18:96] + [
        "Point card deployed. That was not decoration; that was leverage.",
        "I just parked value on the table and dared you to answer.",
        "Those points now travel under Jarvis supervision.",
    ]
)

JARVIS_QUOTES_POINT_HUMAN = _dedupe_quotes(
    JARVIS_QUOTES_HUMAN_GOOD[20:112] + [
        "Doctor Yoba, that point-card timing was very serious business.",
        "Doctor Yoba, you inserted value without losing shape.",
        "Doctor Yoba, that point card had proper escort.",
    ]
)

JARVIS_QUOTES_CUT_AI = _dedupe_quotes(
    JARVIS_QUOTES_AI_GOOD[8:98] + [
        "Cut confirmed. I just revised your plan in real time.",
        "That boridan was deliberate, not decorative.",
        "I removed your lead and inherited your trick.",
    ]
)

JARVIS_QUOTES_CUT_HUMAN = _dedupe_quotes(
    JARVIS_QUOTES_HUMAN_GOOD[10:110] + [
        "Doctor Yoba, that cut had textbook authority.",
        "Doctor Yoba, you just stole initiative with one trump.",
        "Doctor Yoba, that boridan was cold and correct.",
    ]
)

JARVIS_QUOTES_DUMP_AI = _dedupe_quotes(
    JARVIS_QUOTES_AI_BAD[8:86] + [
        "That dump was damage control, not strategy.",
        "I am calling that a tactical retreat with paperwork.",
        "Please treat that discard as temporary confusion.",
    ]
)

JARVIS_QUOTES_DUMP_HUMAN = _dedupe_quotes(
    JARVIS_QUOTES_HUMAN_BAD[10:120] + [
        "Doctor Yoba, that dump conceded more than it saved.",
        "Doctor Yoba, that looked like surrender at card speed.",
        "Doctor Yoba, that discard leaked future control.",
    ]
)

JARVIS_QUOTES_TRUMP_LEAD_AI = _dedupe_quotes(
    JARVIS_QUOTES_AI_GOOD[4:88] + [
        "Sar-e hokm from Jarvis. We are playing serious cards now.",
        "Trump opened. The table is now under direct pressure.",
    ]
)

JARVIS_QUOTES_TRUMP_LEAD_HUMAN = _dedupe_quotes(
    JARVIS_QUOTES_HUMAN_GOOD[4:104] + [
        "Doctor Yoba, leading trump here is excellent command pressure.",
        "Doctor Yoba, that sar-e hokm call was forceful and clean.",
    ]
)

                                                   
                                                                                                                                                                                                                               
PLAY_MODEL = "shelem_play.npz"                                                     
                                                                                                                                                                                                                               
BID_MODEL  = "shelem_bid.npz"                                                     
                                                                                                                                                               
VALUE_MODEL = "shelem_value.npz"                                                       
SHARED_MODEL = "shelem_shared.npz"                                                        
SHARED_NET_LR = 0.00025                                                    
                                                                                                                                                               
HISTORY_FILE = "shelem_history.json"                                                 
SAVE_DB_FILE = "shelem_saves.db"                                                  
GAME_DB_FILE = "shelem_games.db"                                               
TACTICS_DB_FILE = "shelem_tactics.db"
SNAPSHOT_SCHEMA_VERSION = 1                                                       
ASSET_BASE_DIR = os.path.dirname(os.path.abspath(__file__))                                          
CARD_BACK_IMAGE_FILE = "1.png"                                                    
PAYOUT_SOUND_FILE = "poker-.wav"                                                         
SETUP_MUSIC_FILE = "Ugly.mp3"                                   
GAMEPLAY_MUSIC_FILE = "Gold.mp3"                                    
GAMEPLAY_MUSIC_ALT_FILE = "Storm.mp3"                                           
DANGER_MUSIC_FILE = "Jaws.ogg"                                                              
REQUIEM_MUSIC_FILE = "Lacrimosa.mp3"                                                            

                                                                    
                                                                                                                                                               
AI_DELAY_MS = 400                                                           
                                                                                                                                                               
AUTO_TRICK_MS = 1100                                                     
                                                                                                                                                               
AUTO_ROUND_MS = 2500                                                
                                                                                                                                                               
SHELEM_ANIM_MS = 5200                                            

                                                    
                                                                                                                                                               
MIN_BID = 75                                             
                                                                                                                                                               
MAX_BID = 165                                                       
                                                                                                                                                               
TOTAL_PTS = 165                                                  

                                                                   
                                                                                                                                                                                                                           
MC_SAMPLES = 72                                                        
                                                                                                                                                                                                                
MAX_SEARCH_MB = 64                                                     
                                                                                                                                                               
EXPECTI_TEMP = 14.0                                                             
                                                                                                                                                               
BG_SEARCH_SLICE_S = 0.08                                   
                                                                                                                                                                                                                                                              
BG_TREE_DEPTH = 4                                          
                               
PROCESS_MEMORY_CAP_MB = 200
MEMORY_PRESSURE_SOFT_RATIO = 0.82
MEMORY_PRESSURE_HARD_RATIO = 0.90
MEMORY_CHECK_INTERVAL_S = 0.20
TIMELINE_TICK_MIN_MS = 450
SCORE_BAR_H = 108
                                                                                   
SHOW_HUMAN_MOVE_ANALYSIS = False

                                                             
                                                                                                                                                               
BID_NN_SCALE = 55.0                                                                
                                                                                                                                                               
BID_RAISE_MULT_BASE = 0.60                                                         
                                                                                                                                                               
BID_RAISE_MULT_RISK = 0.15                                                  
                                                                                                                                                               
BID_AGGRESSION = 6.0
BID_CAP_BONUS = 40.0                                                                     
BID_CAP_VALUE_SCALE = 12.0                                                            
BID_WEAK_OPEN_PASS = 38.0                                                                
                                                                                                                                                                                                                               
BID_MARGIN_UP_SCALE = 100.0                                                   
                                                                                                                                                               
BID_MARGIN_DOWN_SCALE = 80.0                                                   
                                                                                                                                                                                                                               
BID_SUCCESS_BONUS = 0.35                                         
                                                                                                                                                               
BID_FAIL_PENALTY = 0.70                                           

                                
                                                                                                                                                               
FELT=(28,92,38)
                                                
                                                                                                                                                               
FELT_DARK=(22,72,30)
                                                    
                                                                                                                                                               
FELT_LINE=(36,110,48)
                                                        
                                                                                                                                                               
WHITE=(255,255,255)
                                                           
                                                                                                                                                               
BLACK=(0,0,0)
                                                           
                                                                                                                                                               
RED=(200,30,30)
                                    
BLUE=(30,90,210)
                                  
GREEN=(0,150,70)
                          
                                                                                                                                                               
CARD_BG=(252,250,245)
                                         
                                                                                                                                                               
CARD_BACK=(35,55,130)
                                                  
                                                                                                                                                               
CARD_BACK2=(28,42,105)
                                                   
                                                                                                                                                               
GOLD=(218,185,100)
                                                    
                                                                                                                                                               
GOLD_DIM=(160,140,80)
                                                 
                                                                                                                                                               
DIM_OVERLAY=(0,0,0,90)
                            
                                                                                                                                                               
BTN_NORMAL=(60,60,60)
                             
                                                                                                                                                               
BTN_HOVER=(90,90,90)
                    
                                                                                                                                                               
BTN_TEXT=(240,240,240)
                                         
                                                                                                                                                               
AI_THINK=(100,180,255)
                                        
                                                                                                                                                               
TRUMP_TINT=(150,90,210,120)
                                                             
                                                                                                                                                               
CHIP_COLS={5:(245,245,245),10:(200,40,40),20:(30,120,200),50:(40,160,60),100:(20,20,20)}
                                                             
                                                                                                                                                               
CHIP_EDGE={5:(200,200,200),10:(150,25,25),20:(20,80,160),50:(30,120,45),100:(60,60,60)}

                                                                     
                                                                                                                                                               
SUITS=["\u2660","\u2665","\u2666","\u2663"]
                                           
                                                                                                                                                               
SUIT_COLOUR={"\u2660":BLACK,"\u2665":RED,"\u2666":BLUE,"\u2663":GREEN}
                                           
                                                                                                                                                               
SUIT_NAMES={"\u2660":"Spades","\u2665":"Hearts","\u2666":"Diamonds","\u2663":"Clubs"}
                                                              
PERSIAN_SUIT_NAMES={"\u2660":"Pika","\u2665":"Del","\u2666":"Khesht","\u2663":"Gishniz"}
PERSIAN_RANK_NAMES={
    "A":"Aas","K":"Shah","Q":"Bibi","J":"Golam","10":"Dah","9":"Noh","8":"Hasht",
    "7":"Haft","6":"Shish","5":"Panj","4":"Chahar","3":"Se","2":"Dudu",
}
                                                    
COURT_SYMBOL={}
                                                                        
                                                                                                                                                               
RANKS=["2","3","4","5","6","7","8","9","10","J","Q","K","A"]
                                                  
                                                                                                                                                               
RANK_ORDER={r:i for i,r in enumerate(RANKS)}
                                             
                                                                                                                                                               
ALL_52=set(range(52))

_mem_last_check_t=0.0
_mem_last_rss_mb=None
_mem_last_pressure=0

def _apply_process_memory_limit(limit_mb):
    """Try to cap process memory to reduce whole-machine stalls."""
    if _resource is None:
        return False
    if os.environ.get("SHELEM_HARD_MEM_CAP", "0")!="1":
        return False
    try:
        cap_mb=int(limit_mb)
    except Exception:
        cap_mb=0
    limit_bytes=max(32, cap_mb)*1024*1024
    changed=False
    for attr in ("RLIMIT_DATA", "RLIMIT_RSS"):
        rid=getattr(_resource, attr, None)
        if rid is None:
            continue
        try:
            soft, hard=_resource.getrlimit(rid)
            if hard in (-1, getattr(_resource, "RLIM_INFINITY", -1)):
                new_soft=limit_bytes
            else:
                new_soft=min(limit_bytes, int(hard))
            if soft in (-1, getattr(_resource, "RLIM_INFINITY", -1)) or int(soft)>new_soft:
                _resource.setrlimit(rid, (new_soft, hard))
                changed=True
        except Exception:
            continue
    return changed

def _process_rss_mb():
    """Best-effort current RSS in MB."""
    try:
        with open("/proc/self/status", "r", encoding="ascii", errors="ignore") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    parts=line.split()
                    if len(parts)>=2:
                        return float(parts[1])/1024.0
    except Exception:
        pass
    if _resource is not None:
        try:
            rss_kb=float(_resource.getrusage(_resource.RUSAGE_SELF).ru_maxrss)
            if rss_kb>0:
                return rss_kb/1024.0
        except Exception:
            pass
    return None

def _memory_pressure(force=False):
    """Return (pressure_level, rss_mb). 0=normal,1=soft,2=hard."""
    global _mem_last_check_t, _mem_last_rss_mb, _mem_last_pressure
    now=_time.monotonic()
    if force or (now-_mem_last_check_t)>=MEMORY_CHECK_INTERVAL_S:
        _mem_last_check_t=now
        _mem_last_rss_mb=_process_rss_mb()
        rss=_mem_last_rss_mb
        if rss is None:
            _mem_last_pressure=0
        else:
            ratio=float(rss)/max(1.0, float(PROCESS_MEMORY_CAP_MB))
            if ratio>=MEMORY_PRESSURE_HARD_RATIO:
                _mem_last_pressure=2
            elif ratio>=MEMORY_PRESSURE_SOFT_RATIO:
                _mem_last_pressure=1
            else:
                _mem_last_pressure=0
            if _mem_last_pressure>=1:
                gc.collect(0)
            if _mem_last_pressure>=2:
                gc.collect()
    return _mem_last_pressure, _mem_last_rss_mb

def _refresh_search_node_budget():
    """Adjust minimax node cap to current memory pressure."""
    global _max_nodes
    pressure,_=_memory_pressure()
    if pressure>=2:
        search_mb=max(16, min(MAX_SEARCH_MB, 24))
    elif pressure>=1:
        search_mb=max(24, min(MAX_SEARCH_MB, 40))
    else:
        search_mb=MAX_SEARCH_MB
    _max_nodes=max(1, (search_mb*1024*1024)//400)

                                                                                                                                                  
class State(Enum):
                                                                                                                                                                      
    """Top-level UI/game finite-state-machine states."""
                                                                                                                                                                   
    MATCH_START=auto(); BIDDING=auto(); TAKE_SPECIAL=auto()
                                                                                                                                                                   
    DISCARDING=auto(); TRUMP_SELECT=auto()
                                                                                                                                                                   
    PLAY_HAND_LEADER=auto(); PLAY_HAND_FOLLOWER=auto()
                                                                                                                                                                   
    PLAY_PILE_LEADER=auto(); PLAY_PILE_FOLLOWER=auto()
                                                                                                                                                                   
    TRICK_RESULT=auto(); ROUND_END=auto(); MATCH_OVER=auto()
                                                                                                                                                                   
    SHELEM_CELEBRATION=auto()

                                                                                                                                                  
class Card:
                                                                                                                                                                      
    """Card model with helpers for order, scoring, and trick precedence."""
                                                                                                                                                                   
    __slots__=("suit","rank","face_up")
                                                                   
                                                                                                                                                      
    def __init__(s,suit,rank): s.suit=suit; s.rank=rank; s.face_up=True
                                                     
                                                                                                                                                      
    def order(s): return SUITS.index(s.suit)*13+RANK_ORDER[s.rank]
                                 
                                                                                                                                                      
    def points(s):
                                                                                                                                                                    
        if s.rank=="5": return 5
                                                                                                                                                                    
        if s.rank in("10","A"): return 10
                                                                                                                                                  
        return 0
                                                            
                                                                                                                                                      
    def trick_power(s,led,trump):
                                                                                                                                                                    
        if s.suit==trump: return 200+RANK_ORDER[s.rank]
                                                                                                                                                                    
        if s.suit==led:   return 100+RANK_ORDER[s.rank]
                                                                                                                                                  
        return RANK_ORDER[s.rank]
                                                      
                                                                                                                                                      
    def id52(s): return SUITS.index(s.suit)*13+RANK_ORDER[s.rank]
                                                                                                                                                      
    def __repr__(s): return card_ui_text(s)
                                                                                                                                                      
    def copy(s):
                                                                                                                                                                          
        """Return a detached copy preserving face-up state."""
                                                                                                                                                                       
        c=Card(s.suit,s.rank); c.face_up=s.face_up; return c

                                                                                                                                                  
def id_to_card(i):
                                                                                                                                                        
    """Convert canonical card id (0..51) to a `Card` instance."""
                                                                                                                                                                   
    c=Card(SUITS[i//13],RANKS[i%13]); return c
                                                                                                                                                  
def make_deck():
                                                                                                                                                                      
    """Create and shuffle a standard 52-card deck."""
                                                                                                                                                                   
    d=[Card(s,r) for s in SUITS for r in RANKS]; random.shuffle(d); return d
                                                                                                                                                  
def sort_hand(h):
                                                                                                                                                                      
    """Sort hand cards for stable visual layout and deterministic behavior."""
                                                                                                                                                        
    h.sort(key=lambda c:c.order())
                                                                                                                                                  
def card_points(cards):
                                                                                                                                                                      
    """Return total point value carried by a card list."""
                                                                                                                                              
    return sum(c.points() for c in cards)
                                                                                                                                                  
def count_value(cards):
                                                                                                                                                                      
    """Count how many 5/10/A cards are present in a card collection."""
                                                                                                                                                                   
    c={"5":0,"10":0,"A":0}
                                                                                                                                                                  
    for card in cards:
                                                                                                                                                                    
        if card.rank in c: c[card.rank]+=1
                                                                                                                                              
    return c

                                                                                                                                                  
def player_name(pid):
                                                                                                                                                                      
    """Map player id to configured display name."""
                                                                                                                                              
    return HUMAN_NAME if pid==HUMAN else AI_NAME

def rank_ui_text(rank):
    """Display rank with classic notation."""
    return str(rank)

def card_ui_text(card):
    """Display one card token for UI text."""
    return f"{rank_ui_text(card.rank)}{card.suit}"

def label_to_ui_text(label):
    """Convert plain rank+suit label (e.g. 'Q♣') into decorated UI text."""
    s=(label or "").strip()
    if len(s)<2:
        return s
    suit=s[-1]
    rank=s[:-1]
    if suit in SUITS and rank in RANK_ORDER:
        return f"{rank_ui_text(rank)}{suit}"
    return s

def money_text(amount):
    """Format signed dollars with leading minus when needed."""
    v=_to_int(amount, 0)
    return f"${v}" if v>=0 else f"-${abs(v)}"

                                                                   

def _to_int(v, default=0):
    """Best-effort int conversion used for command parsing and restore."""
    try:
        return int(v)
    except (TypeError, ValueError):
        return default

def _card_to_data(card):
    """Serialize one Card object into JSON-safe data."""
    return {"s": card.suit, "r": card.rank, "u": bool(card.face_up)}

def _card_from_data(data):
    """Deserialize one Card object from JSON-safe data."""
    c=Card(data["s"], data["r"])
    c.face_up=bool(data.get("u", True))
    return c

def _cards_to_data(cards):
    """Serialize a list of Card objects."""
    return [_card_to_data(c) for c in cards]

def _cards_from_data(items):
    """Deserialize a list of Card objects."""
    return [_card_from_data(i) for i in (items or [])]

def _piles_to_data(piles):
    """Serialize nested pile structure."""
    return [[_card_to_data(c) for c in pile] for pile in (piles or [])]

def _piles_from_data(payload):
    """Deserialize nested pile structure."""
    return [[_card_from_data(c) for c in (pile or [])] for pile in (payload or [])]

def _trick_to_data(trick):
    """Serialize one trick [(Card, player), ...]."""
    return [{"card": _card_to_data(card), "player": int(player)} for card,player in trick]

def _trick_from_data(payload):
    """Deserialize one trick [(Card, player), ...]."""
    out=[]
    for item in (payload or []):
        try:
            out.append((_card_from_data(item["card"]), _to_int(item.get("player", 0), 0)))
        except Exception:
            continue
    return out

class SaveStateStore:
    """Manual save/load store backing `/save` and `/load [number]`."""
    def __init__(self, path=SAVE_DB_FILE):
        self.path=path
        self._init_schema()

    def _connect(self):
        conn=sqlite3.connect(self.path)
        conn.row_factory=sqlite3.Row
        return conn

    def _init_schema(self):
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS saved_states (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    snapshot_json TEXT NOT NULL,
                    fsm_state TEXT,
                    round_num INTEGER,
                    trick_num INTEGER
                )
                """
            )

    def save_snapshot(self, snapshot):
        game=snapshot.get("game", {})
        blob=json.dumps(snapshot, separators=(",", ":"), ensure_ascii=True)
        with self._connect() as conn:
            cur=conn.execute(
                """
                INSERT INTO saved_states (snapshot_json, fsm_state, round_num, trick_num)
                VALUES (?, ?, ?, ?)
                """,
                (
                    blob,
                    game.get("state"),
                    _to_int(game.get("round_num", 0), 0),
                    _to_int(game.get("trick_num", 0), 0),
                ),
            )
            return int(cur.lastrowid)

    def load_snapshot(self, save_id):
        with self._connect() as conn:
            row=conn.execute(
                "SELECT snapshot_json FROM saved_states WHERE id=?",
                (_to_int(save_id, -1),),
            ).fetchone()
        if not row:
            return None
        try:
            return json.loads(row["snapshot_json"])
        except Exception:
            return None

class GameTimelineStore:
    """Full game timeline database (games + every consecutive state)."""
    def __init__(self, path=GAME_DB_FILE):
        self.path=path
        self._init_schema()

    def _connect(self):
        conn=sqlite3.connect(self.path)
        conn.row_factory=sqlite3.Row
        return conn

    def _init_schema(self):
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS games (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    ended_at TEXT,
                    origin TEXT,
                    source_save_id INTEGER,
                    source_game_id INTEGER,
                    source_state_num INTEGER,
                    match_target INTEGER,
                    time_minutes INTEGER,
                    winner INTEGER,
                    final_score_a INTEGER,
                    final_score_b INTEGER,
                    rounds INTEGER,
                    final_state TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS game_states (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    game_id INTEGER NOT NULL,
                    state_num INTEGER NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    reason TEXT,
                    fsm_state TEXT,
                    round_num INTEGER,
                    trick_num INTEGER,
                    score_a INTEGER,
                    score_b INTEGER,
                    snapshot_json TEXT NOT NULL,
                    UNIQUE(game_id, state_num)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_game_states_gid_num ON game_states (game_id, state_num)"
            )

    def create_game(self, match_target, time_minutes, origin,
                    source_save_id=None, source_game_id=None, source_state_num=None):
        with self._connect() as conn:
            cur=conn.execute(
                """
                INSERT INTO games (
                    origin, source_save_id, source_game_id, source_state_num, match_target, time_minutes
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    origin,
                    source_save_id,
                    source_game_id,
                    source_state_num,
                    _to_int(match_target, 0),
                    _to_int(time_minutes, 0),
                ),
            )
            return int(cur.lastrowid)

    def append_state(self, game_id, state_num, snapshot, reason="auto"):
        game=snapshot.get("game", {})
        blob=json.dumps(snapshot, separators=(",", ":"), ensure_ascii=True)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO game_states (
                    game_id, state_num, reason, fsm_state, round_num, trick_num, score_a, score_b, snapshot_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    _to_int(game_id, -1),
                    _to_int(state_num, 0),
                    reason,
                    game.get("state"),
                    _to_int(game.get("round_num", 0), 0),
                    _to_int(game.get("trick_num", 0), 0),
                    _to_int((game.get("scores") or [0, 0])[0], 0),
                    _to_int((game.get("scores") or [0, 0])[1], 0),
                    blob,
                ),
            )

    def update_game_progress(self, game_id, snapshot):
        game=snapshot.get("game", {})
        scores=game.get("scores") or [0, 0]
        state=game.get("state")
        winner=game.get("match_winner")
        ended_at="CURRENT_TIMESTAMP" if winner is not None or state==State.MATCH_OVER.name else None
        with self._connect() as conn:
            if ended_at:
                conn.execute(
                    """
                    UPDATE games
                    SET winner=?, final_score_a=?, final_score_b=?, rounds=?, final_state=?, ended_at=CURRENT_TIMESTAMP
                    WHERE id=?
                    """,
                    (
                        _to_int(winner, -1),
                        _to_int(scores[0], 0),
                        _to_int(scores[1], 0),
                        _to_int(game.get("round_num", 0), 0),
                        state,
                        _to_int(game_id, -1),
                    ),
                )
            else:
                conn.execute(
                    """
                    UPDATE games
                    SET winner=NULL, final_score_a=?, final_score_b=?, rounds=?, final_state=?
                    WHERE id=?
                    """,
                    (
                        _to_int(scores[0], 0),
                        _to_int(scores[1], 0),
                        _to_int(game.get("round_num", 0), 0),
                        state,
                        _to_int(game_id, -1),
                    ),
                )

    def list_games(self, limit=300):
        with self._connect() as conn:
            rows=conn.execute(
                """
                SELECT
                    g.id, g.started_at, g.ended_at, g.origin, g.match_target, g.time_minutes,
                    g.winner, g.final_score_a, g.final_score_b, g.rounds, g.final_state,
                    COALESCE(s.state_count, 0) AS states_count,
                    CASE WHEN COALESCE(s.state_count, 0) > 0 THEN s.state_count - 1 ELSE 0 END AS moves_count,
                    ls.state_num AS latest_state_num,
                    ls.fsm_state AS latest_fsm_state,
                    ls.round_num AS latest_round_num,
                    ls.trick_num AS latest_trick_num
                FROM games g
                LEFT JOIN (
                    SELECT game_id, COUNT(*) AS state_count, MAX(state_num) AS max_state
                    FROM game_states
                    GROUP BY game_id
                ) s ON s.game_id=g.id
                LEFT JOIN game_states ls ON ls.game_id=g.id AND ls.state_num=s.max_state
                ORDER BY g.id DESC
                LIMIT ?
                """,
                (_to_int(limit, 300),),
            ).fetchall()
        out=[]
        for r in rows:
            out.append({k: r[k] for k in r.keys()})
        return out

    def load_game_state(self, game_id, state_num):
        with self._connect() as conn:
            row=conn.execute(
                """
                SELECT snapshot_json
                FROM game_states
                WHERE game_id=? AND state_num=?
                """,
                (_to_int(game_id, -1), _to_int(state_num, -1)),
            ).fetchone()
        if not row:
            return None
        try:
            return json.loads(row["snapshot_json"])
        except Exception:
            return None

    def load_game_states(self, game_id):
        with self._connect() as conn:
            rows=conn.execute(
                """
                SELECT state_num, snapshot_json
                FROM game_states
                WHERE game_id=?
                ORDER BY state_num ASC
                """,
                (_to_int(game_id, -1),),
            ).fetchall()
        out=[]
        for r in rows:
            try:
                out.append((_to_int(r["state_num"], 0), json.loads(r["snapshot_json"])))
            except Exception:
                continue
        return out

class TacticGradeStore:
    """Dedicated database for user-graded tactics/moves."""
    VALID_GRADES=("bad", "neutral", "good", "excellent")

    def __init__(self, path=TACTICS_DB_FILE):
        self.path=path
        self._init_schema()

    def _connect(self):
        conn=sqlite3.connect(self.path)
        conn.row_factory=sqlite3.Row
        return conn

    def _init_schema(self):
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tactic_grades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    game_id INTEGER,
                    from_state_num INTEGER,
                    to_state_num INTEGER,
                    state_code TEXT,
                    round_num INTEGER,
                    trick_num INTEGER,
                    fsm_state TEXT,
                    actor INTEGER,
                    bid_amount INTEGER,
                    bid_winner INTEGER,
                    trump_suit TEXT,
                    score_a INTEGER,
                    score_b INTEGER,
                    grade TEXT NOT NULL,
                    source_mode TEXT,
                    move_summary TEXT,
                    from_snapshot_json TEXT,
                    to_snapshot_json TEXT,
                    UNIQUE(game_id, to_state_num)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_tactic_grades_created ON tactic_grades (id DESC)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_tactic_grades_grade ON tactic_grades (grade)"
            )

    def save_grade(self, payload):
        row=dict(payload or {})
        grade=str(row.get("grade", "")).strip().lower()
        if grade not in self.VALID_GRADES:
            raise ValueError("Invalid tactic grade.")
        game_id=_to_int(row.get("game_id", 0), 0)
        from_state_num=_to_int(row.get("from_state_num", 0), 0)
        to_state_num=_to_int(row.get("to_state_num", 0), 0)
        if game_id<=0 or to_state_num<=0:
            raise ValueError("Invalid graded move target.")
        from_snap=json.dumps(row.get("from_snapshot") or {}, separators=(",", ":"), ensure_ascii=True)
        to_snap=json.dumps(row.get("to_snapshot") or {}, separators=(",", ":"), ensure_ascii=True)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO tactic_grades (
                    game_id, from_state_num, to_state_num, state_code,
                    round_num, trick_num, fsm_state, actor, bid_amount, bid_winner, trump_suit,
                    score_a, score_b, grade, source_mode, move_summary,
                    from_snapshot_json, to_snapshot_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(game_id, to_state_num) DO UPDATE SET
                    from_state_num=excluded.from_state_num,
                    state_code=excluded.state_code,
                    round_num=excluded.round_num,
                    trick_num=excluded.trick_num,
                    fsm_state=excluded.fsm_state,
                    actor=excluded.actor,
                    bid_amount=excluded.bid_amount,
                    bid_winner=excluded.bid_winner,
                    trump_suit=excluded.trump_suit,
                    score_a=excluded.score_a,
                    score_b=excluded.score_b,
                    grade=excluded.grade,
                    source_mode=excluded.source_mode,
                    move_summary=excluded.move_summary,
                    from_snapshot_json=excluded.from_snapshot_json,
                    to_snapshot_json=excluded.to_snapshot_json,
                    created_at=CURRENT_TIMESTAMP
                """,
                (
                    game_id,
                    from_state_num,
                    to_state_num,
                    row.get("state_code"),
                    _to_int(row.get("round_num", 0), 0),
                    _to_int(row.get("trick_num", 0), 0),
                    row.get("fsm_state"),
                    row.get("actor"),
                    _to_int(row.get("bid_amount", 0), 0),
                    row.get("bid_winner"),
                    row.get("trump_suit"),
                    _to_int(row.get("score_a", 0), 0),
                    _to_int(row.get("score_b", 0), 0),
                    grade,
                    row.get("source_mode"),
                    row.get("move_summary"),
                    from_snap,
                    to_snap,
                ),
            )
            id_row=conn.execute(
                "SELECT id FROM tactic_grades WHERE game_id=? AND to_state_num=?",
                (game_id, to_state_num),
            ).fetchone()
            return _to_int(id_row["id"], 0) if id_row else 0

    def grade_summary(self):
        counts={g: 0 for g in self.VALID_GRADES}
        with self._connect() as conn:
            rows=conn.execute(
                "SELECT grade, COUNT(*) AS c FROM tactic_grades GROUP BY grade"
            ).fetchall()
        for r in rows:
            g=str(r["grade"] or "").strip().lower()
            if g in counts:
                counts[g]=_to_int(r["c"], 0)
        return counts

    def list_recent(self, limit=20):
        with self._connect() as conn:
            rows=conn.execute(
                """
                SELECT
                    id, created_at, game_id, from_state_num, to_state_num,
                    state_code, round_num, trick_num, fsm_state,
                    score_a, score_b, grade, move_summary
                FROM tactic_grades
                ORDER BY id DESC
                LIMIT ?
                """,
                (_to_int(limit, 20),),
            ).fetchall()
        return [{k: r[k] for k in r.keys()} for r in rows]

                                                                   

                                                                                                                                                  
def _wav(sr,dur,fn):
                                                                                                                                                                      
    """Synthesize a mono WAV buffer from a waveform callback."""
                                                                                                                                                                   
    n=int(sr*dur); buf=array.array('h',[0]*n)
                                                                                                                                                                  
    for i in range(n): buf[i]=max(-32767,min(32767,int(fn(i,sr,dur)*28000)))
                                                                                                                                                                   
    raw=buf.tobytes()
                                                                                                                                                                   
    hdr=struct.pack('<4sI4s',b'RIFF',36+len(raw),b'WAVE')
                                                                                                                                                                   
    fmt=struct.pack('<4sIHHIIHH',b'fmt ',16,1,1,sr,sr*2,2,16)
                                                                                                                                                                   
    dat=struct.pack('<4sI',b'data',len(raw))
                                                                                                                                                                   
    w=io.BytesIO(hdr+fmt+dat+raw); w.seek(0); return w
                                                                                                                                                  
def _card_snd(i,sr,d):
                                                                                                                                                                      
    """Short noisy click used for card-play sound effect."""
                                                                                                                                                                   
    t=i/sr; e=max(0,1-t/d)**3
                                                                                                                                              
    return (math.sin(6283*t)*0.4+(random.random()*2-1)*0.6*max(0,1-t/0.02))*e
                                                                                                                                                  
def _chip_snd(i,sr,d):
                                                                                                                                                                      
    """Metallic chip-like sound used for bid increments."""
                                                                                                                                                                   
    t=i/sr; e=max(0,1-t/d)**2
                                                                                                                                              
    return (math.sin(7540*t)*0.3*max(0,1-t/0.01)+math.sin(3770*t)*0.4*max(0,1-t/0.04)*e
                                                                                                                                                                
            +(random.random()*2-1)*0.3*max(0,1-t/0.06)*e)

def _payout_snd(i,sr,d):
    """Soft stacked-chip clink used for score payouts."""
    t=i/sr
    e=max(0,1-t/d)**1.7
    return (math.sin(2*math.pi*1730*t)*0.28*max(0,1-t/0.05) +
            math.sin(2*math.pi*1110*t)*0.22*max(0,1-t/0.09) +
            (random.random()*2-1)*0.16*max(0,1-t/0.03))*e
                                                                                                                                                  
def _fan_snd(i,sr,d):
                                                                                                                                                                      
    """Soft two-tone fanfare used for celebratory moments."""
                                                                                                                                                                   
    t=i/sr; e=max(0,1-t/d)**1.5
                                                                                                                                              
    return (math.sin(2*math.pi*440*(1+t*0.5)*t)*0.3+math.sin(2*math.pi*660*(1+t*0.3)*t)*0.3)*e

                                                                   

                                                                                                                                                  
class ChessClock:
                                                                                                                                                                      
    """Two-side countdown clock used for move timing and timeouts."""
                                                                                                                                                      
    def __init__(s,a=600,b=600):
                                                                                                                                                            
        s.initial=[float(a),float(b)]
                                                                                                                                                            
        s.rem=[float(a),float(b)]; s.active=None; s._t=None; s.flagged=[False,False]
                                         
                                                                                                                                                      
    def start(s,p): s.active=p; s._t=_time.monotonic()
                                   
                                                                                                                                                      
    def switch_to(s,p): s.update(); s.active=p; s._t=_time.monotonic()
                        
                                                                                                                                                      
    def pause(s): s.update(); s.active=None
                                                                                                                                                      
    def update(s):
                                                                                                                                                                          
        """Consume elapsed wall time from active side and set flag on timeout."""
                                                                                                                                                                    
        if s.active is not None and s._t is not None:
                                                                                                                                                                           
            n=_time.monotonic(); s.rem[s.active]-=n-s._t; s._t=n
                                                                                                                                                                        
            if s.rem[s.active]<=0: s.rem[s.active]=0; s.flagged[s.active]=True
                                                                                                                                                      
    def fmt(s,p):
                                                                                                                                                                          
        """Format remaining time as MM:SS string."""
                                                                                                                                                                       
        t=max(0,s.rem[p]); return f"{int(t)//60:02d}:{int(t)%60:02d}"
                                                                                                                                                      
    def reset(s,a,b):
                                                                                                                                                                          
        """Reset both clocks to new initial values."""
                                                                                                                                                            
        s.initial=[float(a),float(b)]
                                                                                                                                                            
        s.rem=[float(a),float(b)]; s.active=None; s._t=None; s.flagged=[False,False]
                                                                                                                                                      
    def reset_round(s):
                                                                                                                                                                          
        """Reset current round timers back to stored initial values."""
                                                                                                                                                            
        s.rem=list(s.initial); s.active=None; s._t=None; s.flagged=[False,False]

                                                                   

                                                                                                                                                                                                                       
def relu(x):
                                                                                                                                                                                                                                           
    """ReLU activation for hidden layers."""
                                                                                                                                              
    return np.maximum(0,x)
                                                                                                                                                                                                                       
def relu_d(x):
                                                                                                                                                                                                                                                                                          
    """Derivative of ReLU used in backpropagation."""
                                                                                                                                              
    return (x>0).astype(np.float64)

                                                                                                                                                                                                                     
class NeuralNet:
                                                                                                                                                                      
    """Variable-depth MLP."""
                                                                                                                                                      
    def __init__(self, sizes, lr=0.001):
                                                                                                                                                                          
        self.lr=lr; self.W=[]; self.b=[]; self.train_steps=0
                                                                                                                                                                      
        for i in range(len(sizes)-1):
                                                                                                                                                                           
            s=np.sqrt(2.0/sizes[i])
                                                                                                                                                                
            self.W.append(np.random.randn(sizes[i],sizes[i+1]).astype(np.float64)*s)
                                                                                                                                                                
            self.b.append(np.zeros(sizes[i+1],dtype=np.float64))
                                                                                                                                                      
    def forward(self,x):
                                                                                                                                                                          
        """Run forward inference and cache intermediates for training."""
                                                                                                                                                                       
        acts=[x]; zs=[]
                                                                                                                                                                       
        a=x
                                                                                                                                                                      
        for i,(w,b) in enumerate(zip(self.W,self.b)):
                                                                                                                                                                           
            z=a@w+b; zs.append(z)
                                                                                                                                                                                                                                                
            a=relu(z) if i<len(self.W)-1 else z
                                                                                                                                                                
            acts.append(a)
                                                                                                                                                  
        return a.squeeze(-1),(acts,zs)
                                                                                                                                                                                                               
    def backward(self,cache,target):
                                                                                                                                                                                                                                    
        """Run one MSE gradient step; supports scalar or batched targets."""
                                                                                                                                                                       
        acts,zs=cache; x=acts[0]
                                                                                                                                                                    
        if x.ndim<2:
                                                                                                                                                                           
            acts=[a.reshape(1,-1) if a.ndim<2 else a for a in acts]
                                                                                                                                                                           
            zs=[z.reshape(1,-1) if z.ndim<2 else z for z in zs]
                                                                                                                                                                           
            target=np.array([target],dtype=np.float64)
                                                                                                                                                   
        else: target=np.asarray(target,dtype=np.float64)
                                                                                                                                                                       
        m=acts[0].shape[0]; out=acts[-1].squeeze(-1)
                                                                                                                                                                       
        loss=np.mean((out-target)**2)
                                                                                                                                                                       
        da=(2./m)*(out-target).reshape(-1,1)
                                                                                                                                                                      
        for i in range(len(self.W)-1,-1,-1):
                                                                                                                                                                           
            dW=acts[i].T@da; db=da.sum(0)
                                                                                                                                                                
            np.clip(dW,-1,1,out=dW); np.clip(db,-1,1,out=db)
                                                                                                                                                                              
            self.W[i]-=self.lr*dW; self.b[i]-=self.lr*db
                                                                                                                                                                        
            if i>0:
                                                                                                                                                                                                                                                    
                da=(da@self.W[i].T)*relu_d(zs[i-1])
                                                                                                                                                                          
        self.train_steps+=1; return loss
                                                                                                                                                      
    def predict(self,x):
                                                                                                                                                                          
        """Inference helper returning scalar for single-output calls."""
                                                                                                                                                                       
        v,_=self.forward(np.asarray(x,dtype=np.float64))
                                                                                                                                                  
        return float(v) if np.ndim(v)==0 else v
                                                                                                                                                      
    def save(self,path):
                                                                                                                                                                          
        """Persist train step + layer weights to a `.npz` checkpoint."""
                                                                                                                                                                       
        d={'steps':np.array([self.train_steps]),'nlayers':np.array([len(self.W)])}
                                                                                                                                                                      
        for i,(w,b) in enumerate(zip(self.W,self.b)):
                                                                                                                                                                              
            d[f'W{i}']=w; d[f'b{i}']=b
                                                                                                                                                            
        np.savez(path,**d)
                                                                                                                                                      
    def load(self,path):
                                                                                                                                                                          
        """Load checkpoint if file exists and layer shapes match."""
                                                                                                                                                                    
        if not os.path.exists(path): return False
                                                                                                                                                                       
        d=np.load(path); nl=int(d['nlayers'][0])
                                                                                                                                                                    
        if nl!=len(self.W): return False
                                                                                                                                                                      
        for i in range(nl):
                                                                                                                                                                        
            if f'W{i}' in d and d[f'W{i}'].shape==self.W[i].shape:
                                                                                                                                                                                  
                self.W[i]=d[f'W{i}']; self.b[i]=d[f'b{i}']
                                                                                                                                                            
        self.train_steps=int(d['steps'][0]) if 'steps' in d else 0
                                                                                                                                                  
        return True

def _softmax_rows(x):
    """Row-wise numerically stable softmax."""
    x=np.asarray(x, dtype=np.float64)
    if x.ndim==1:
        x=x.reshape(1, -1)
    z=x-np.max(x, axis=1, keepdims=True)
    np.exp(z, out=z)
    den=np.sum(z, axis=1, keepdims=True)+1e-12
    return z/den


class SharedMultiHeadNet:
    """Shared residual MLP with bid/hand/pile policy heads and a match-value head."""
    def __init__(self, input_dim, bid_dim, hand_dim=12, pile_dim=4, width=256, n_blocks=6, lr=0.00025):
        self.input_dim=int(input_dim)
        self.bid_dim=int(bid_dim)
        self.hand_dim=int(hand_dim)
        self.pile_dim=int(pile_dim)
        self.width=int(width)
        self.n_blocks=int(n_blocks)
        self.lr=float(lr)
        self.train_steps=0

        s=np.sqrt(2.0/max(1, self.input_dim))
        self.W_in=np.random.randn(self.input_dim, self.width).astype(np.float64)*s
        self.b_in=np.zeros(self.width, dtype=np.float64)

        self.blocks=[]
        for _ in range(self.n_blocks):
            sb=np.sqrt(2.0/max(1, self.width))
            self.blocks.append({
                "W1": np.random.randn(self.width, self.width).astype(np.float64)*sb,
                "b1": np.zeros(self.width, dtype=np.float64),
                "W2": np.random.randn(self.width, self.width).astype(np.float64)*sb,
                "b2": np.zeros(self.width, dtype=np.float64),
            })

        sh=np.sqrt(2.0/max(1, self.width))
        self.W_bid=np.random.randn(self.width, self.bid_dim).astype(np.float64)*sh
        self.b_bid=np.zeros(self.bid_dim, dtype=np.float64)
        self.W_hand=np.random.randn(self.width, self.hand_dim).astype(np.float64)*sh
        self.b_hand=np.zeros(self.hand_dim, dtype=np.float64)
        self.W_pile=np.random.randn(self.width, self.pile_dim).astype(np.float64)*sh
        self.b_pile=np.zeros(self.pile_dim, dtype=np.float64)
        self.W_value=np.random.randn(self.width, 1).astype(np.float64)*sh
        self.b_value=np.zeros(1, dtype=np.float64)

    def _forward(self, x):
        x=np.asarray(x, dtype=np.float64)
        if x.ndim==1:
            x=x.reshape(1, -1)
        zin=x@self.W_in+self.b_in
        h=relu(zin)
        block_cache=[]
        for blk in self.blocks:
            z1=h@blk["W1"]+blk["b1"]
            a1=relu(z1)
            z2=a1@blk["W2"]+blk["b2"]
            hpre=h+z2
            hout=relu(hpre)
            block_cache.append((h, z1, a1, hpre))
            h=hout
        bid_logits=h@self.W_bid+self.b_bid
        hand_logits=h@self.W_hand+self.b_hand
        pile_logits=h@self.W_pile+self.b_pile
        value_raw=h@self.W_value+self.b_value
        value=np.tanh(value_raw)
        cache=(x, zin, block_cache, h, value_raw)
        return {
            "bid_logits": bid_logits,
            "hand_logits": hand_logits,
            "pile_logits": pile_logits,
            "value": value.squeeze(-1),
        }, cache

    def infer(self, x):
        out,_=self._forward(x)
        return {
            "bid_logits": out["bid_logits"].reshape(-1),
            "hand_logits": out["hand_logits"].reshape(-1),
            "pile_logits": out["pile_logits"].reshape(-1),
            "bid_probs": _softmax_rows(out["bid_logits"]).reshape(-1),
            "hand_probs": _softmax_rows(out["hand_logits"]).reshape(-1),
            "pile_probs": _softmax_rows(out["pile_logits"]).reshape(-1),
            "value": float(out["value"].reshape(-1)[0]),
        }

    def train_step(self, x, policy_head=None, action_idx=None, value_target=None,
                   policy_weight=1.0, value_weight=0.3):
        out,cache=self._forward(x)
        x_in, zin, block_cache, h_last, value_raw=cache
        m=x_in.shape[0]

        d_bid=np.zeros_like(out["bid_logits"])
        d_hand=np.zeros_like(out["hand_logits"])
        d_pile=np.zeros_like(out["pile_logits"])
        d_value_raw=np.zeros((m,1), dtype=np.float64)

        pol_loss=0.0
        if policy_head is not None and action_idx is not None:
            a=int(action_idx)
            if policy_head=="bid" and 0<=a<self.bid_dim:
                p=_softmax_rows(out["bid_logits"])
                pol_loss=float(-np.log(max(1e-12, p[0, a])))
                d_bid=p
                d_bid[0, a]-=1.0
                d_bid*=float(policy_weight)/max(1, m)
            elif policy_head=="hand" and 0<=a<self.hand_dim:
                p=_softmax_rows(out["hand_logits"])
                pol_loss=float(-np.log(max(1e-12, p[0, a])))
                d_hand=p
                d_hand[0, a]-=1.0
                d_hand*=float(policy_weight)/max(1, m)
            elif policy_head=="pile" and 0<=a<self.pile_dim:
                p=_softmax_rows(out["pile_logits"])
                pol_loss=float(-np.log(max(1e-12, p[0, a])))
                d_pile=p
                d_pile[0, a]-=1.0
                d_pile*=float(policy_weight)/max(1, m)

        val_loss=0.0
        if value_target is not None:
            y=float(value_target)
            v=out["value"].reshape(-1, 1)
            err=v-y
            val_loss=float(np.mean(err**2))
            d_value_raw=(2.0/max(1, m))*err*(1.0-np.tanh(value_raw)**2)*float(value_weight)

        dW_bid=h_last.T@d_bid; db_bid=d_bid.sum(0)
        dW_hand=h_last.T@d_hand; db_hand=d_hand.sum(0)
        dW_pile=h_last.T@d_pile; db_pile=d_pile.sum(0)
        dW_value=h_last.T@d_value_raw; db_value=d_value_raw.sum(0)

        dh=d_bid@self.W_bid.T + d_hand@self.W_hand.T + d_pile@self.W_pile.T + d_value_raw@self.W_value.T

        blk_grads=[]
        for bi in range(self.n_blocks-1, -1, -1):
            h_in,z1,a1,hpre=block_cache[bi]
            blk=self.blocks[bi]
            dhpre=dh*relu_d(hpre)
            dz2=dhpre
            dh_in=dhpre.copy()
            dW2=a1.T@dz2; db2=dz2.sum(0)
            da1=dz2@blk["W2"].T
            dz1=da1*relu_d(z1)
            dW1=h_in.T@dz1; db1=dz1.sum(0)
            dh_in+=dz1@blk["W1"].T
            blk_grads.append((bi,dW1,db1,dW2,db2))
            dh=dh_in

        dz_in=dh*relu_d(zin)
        dW_in=x_in.T@dz_in; db_in=dz_in.sum(0)

        def _clip(g):
            np.clip(g, -1.0, 1.0, out=g)
            return g

        self.W_bid-=self.lr*_clip(dW_bid); self.b_bid-=self.lr*_clip(db_bid)
        self.W_hand-=self.lr*_clip(dW_hand); self.b_hand-=self.lr*_clip(db_hand)
        self.W_pile-=self.lr*_clip(dW_pile); self.b_pile-=self.lr*_clip(db_pile)
        self.W_value-=self.lr*_clip(dW_value); self.b_value-=self.lr*_clip(db_value)
        for bi,dW1,db1,dW2,db2 in blk_grads:
            blk=self.blocks[bi]
            blk["W1"]-=self.lr*_clip(dW1); blk["b1"]-=self.lr*_clip(db1)
            blk["W2"]-=self.lr*_clip(dW2); blk["b2"]-=self.lr*_clip(db2)
        self.W_in-=self.lr*_clip(dW_in); self.b_in-=self.lr*_clip(db_in)

        self.train_steps+=1
        return pol_loss, val_loss

    def save(self, path):
        d={
            "train_steps": np.array([self.train_steps], dtype=np.int64),
            "input_dim": np.array([self.input_dim], dtype=np.int64),
            "bid_dim": np.array([self.bid_dim], dtype=np.int64),
            "hand_dim": np.array([self.hand_dim], dtype=np.int64),
            "pile_dim": np.array([self.pile_dim], dtype=np.int64),
            "width": np.array([self.width], dtype=np.int64),
            "n_blocks": np.array([self.n_blocks], dtype=np.int64),
            "lr": np.array([self.lr], dtype=np.float64),
            "W_in": self.W_in, "b_in": self.b_in,
            "W_bid": self.W_bid, "b_bid": self.b_bid,
            "W_hand": self.W_hand, "b_hand": self.b_hand,
            "W_pile": self.W_pile, "b_pile": self.b_pile,
            "W_value": self.W_value, "b_value": self.b_value,
        }
        for i,blk in enumerate(self.blocks):
            d[f"b{i}_W1"]=blk["W1"]; d[f"b{i}_b1"]=blk["b1"]
            d[f"b{i}_W2"]=blk["W2"]; d[f"b{i}_b2"]=blk["b2"]
        np.savez(path, **d)

    def load(self, path):
        if not os.path.exists(path):
            return False
        d=np.load(path)
        try:
            if int(d["input_dim"][0])!=self.input_dim or int(d["bid_dim"][0])!=self.bid_dim:
                return False
            if int(d["hand_dim"][0])!=self.hand_dim or int(d["pile_dim"][0])!=self.pile_dim:
                return False
            if int(d["width"][0])!=self.width or int(d["n_blocks"][0])!=self.n_blocks:
                return False
            self.W_in=d["W_in"]; self.b_in=d["b_in"]
            self.W_bid=d["W_bid"]; self.b_bid=d["b_bid"]
            self.W_hand=d["W_hand"]; self.b_hand=d["b_hand"]
            self.W_pile=d["W_pile"]; self.b_pile=d["b_pile"]
            self.W_value=d["W_value"]; self.b_value=d["b_value"]
            for i in range(self.n_blocks):
                blk=self.blocks[i]
                blk["W1"]=d[f"b{i}_W1"]; blk["b1"]=d[f"b{i}_b1"]
                blk["W2"]=d[f"b{i}_W2"]; blk["b2"]=d[f"b{i}_b2"]
            self.train_steps=int(d["train_steps"][0]) if "train_steps" in d else 0
            return True
        except Exception:
            return False

                                                                   

                                                                                                                                                  
class HumanProfile:
    """Statistical model of the human opponent built from game history.

    Loaded once at startup and updated at match end.  Used by JarvisAI to
    calibrate bidding posture and opening-lead strategy.
    """

    def __init__(self, db_path=GAME_DB_FILE):
        self.win_rate=0.0            # fraction of finished matches human won
        self.bust_rate=0.15          # fraction of rounds human busted contract
        self.avg_score_per_match=250.0
        self.tends_overbid=False     # True when bust_rate > 0.25
        self._load(db_path)

    def _load(self, db_path):
        try:
            import sqlite3 as _sqlite3
            con=_sqlite3.connect(db_path)
            cur=con.cursor()
            rows=cur.execute(
                "SELECT winner, final_score_a, final_score_b FROM games "
                "WHERE winner IS NOT NULL AND final_score_a IS NOT NULL"
            ).fetchall()
            con.close()
            if not rows:
                return
            human_wins=sum(1 for w,_,_ in rows if int(w)==HUMAN)
            self.win_rate=human_wins/len(rows)
            scores=[int(sa) for _,sa,_ in rows]
            self.avg_score_per_match=sum(scores)/len(scores)
            # Approximate bust rate: matches where human score < 0
            negative=sum(1 for _,sa,_ in rows if int(sa)<0)
            self.bust_rate=negative/len(rows)
            self.tends_overbid=self.bust_rate>0.20
        except Exception:
            pass  # DB unavailable — keep defaults


class RoundPlan:
    """Lightweight pre-round plan built before trick 1.

    Jarvis consults this every trick to stay aligned with a round-level
    strategy rather than making purely greedy local decisions.
    """

    POSTURE_NORMAL    = "normal"
    POSTURE_ATTACKING = "attacking"   # Jarvis needs to catch up
    POSTURE_DEFENDING = "defending"   # Jarvis leads — let human overbid

    def __init__(self):
        self.posture=self.POSTURE_NORMAL
        self.is_bidder=False
        self.trump_suit=None
        # Ordered list of strategic goals for this round
        self.phase_goals=[]         # e.g. ["draw_trump","establish_spades","cash"]
        # Maximum trump cards to spend in tricks 1-8 (save rest for endgame)
        self.trump_budget=2
        # Non-trump suits where we hold a running winner (A or solid K)
        self.suits_to_establish=[]
        # (suit, rank) pairs we should AVOID leading into (opponent likely holds higher)
        self.honor_guards=set()
        # Preferred suit/rank for trick-1 lead
        self.opening_lead_suit=None
        self.opening_lead_rank=None
        # How many tricks needed to make the contract
        self.contract_tricks_needed=0

    @classmethod
    def build(cls, hand, trump_suit, bid_amount, is_bidder, game, tracker):
        """Heuristic round plan — O(n) over 12 cards, called once per round."""
        plan=cls()
        plan.trump_suit=trump_suit
        plan.is_bidder=is_bidder

        # ── Game posture ──────────────────────────────────────────────────
        ai_score=int(game.scores[AI_PLAYER])
        hu_score=int(game.scores[HUMAN])
        gap=ai_score-hu_score
        if gap>=300:
            plan.posture=cls.POSTURE_DEFENDING
        elif gap<=-200:
            plan.posture=cls.POSTURE_ATTACKING
        else:
            plan.posture=cls.POSTURE_NORMAL

        # ── Hand analysis ─────────────────────────────────────────────────
        from collections import Counter
        suit_count=Counter(c.suit for c in hand)
        suit_top={s: max((c for c in hand if c.suit==s), key=lambda c: RANK_ORDER[c.rank], default=None)
                  for s in SUITS}

        trump_len=suit_count.get(trump_suit, 0)
        plan.trump_budget=max(1, trump_len-3)   # keep 3 trump for endgame
        plan.contract_tricks_needed=max(0, int(bid_amount)-85)//10+8 if bid_amount else 0

        # ── Suits to establish ────────────────────────────────────────────
        for s in SUITS:
            if s==trump_suit:
                continue
            cnt=suit_count.get(s, 0)
            top=suit_top.get(s)
            if top and cnt>=3 and top.rank in ("A","K"):
                plan.suits_to_establish.append(s)

        # ── Honor guards: suit where opponent likely holds a higher card ──
        opp_honors=tracker.honor_played_by_opp if hasattr(tracker,"honor_played_by_opp") else set()
        for s in SUITS:
            top=suit_top.get(s)
            if not top:
                continue
            # If opponent has shown an Ace in this suit and we only hold K/Q, guard it
            if ("A",s) not in opp_honors and top.rank in ("K","Q"):
                # Opponent probably has Ace: avoid leading into it
                plan.honor_guards.add((s, top.rank))

        # ── Phase goals ───────────────────────────────────────────────────
        if is_bidder:
            if trump_len>=5:
                plan.phase_goals.append("draw_trump")
            if plan.suits_to_establish:
                plan.phase_goals.append(f"establish_{plan.suits_to_establish[0]}")
            plan.phase_goals.append("cash_winners")
        else:
            plan.phase_goals.append("break_contract")
            plan.phase_goals.append("preserve_points")

        # ── Opening lead recommendation ───────────────────────────────────
        if is_bidder:
            if trump_len>=6:
                plan.opening_lead_suit=trump_suit
                plan.opening_lead_rank=max(
                    (c for c in hand if c.suit==trump_suit),
                    key=lambda c: RANK_ORDER[c.rank]
                ).rank
            elif plan.suits_to_establish:
                est=plan.suits_to_establish[0]
                plan.opening_lead_suit=est
                plan.opening_lead_rank=max(
                    (c for c in hand if c.suit==est),
                    key=lambda c: RANK_ORDER[c.rank]
                ).rank
        else:
            # Defender: lead longest plain suit to exhaust bidder's trumps early
            best=max(
                ((s,cnt) for s,cnt in suit_count.items() if s!=trump_suit and cnt>=2),
                key=lambda sc: sc[1], default=(None, 0)
            )
            if best[0]:
                plan.opening_lead_suit=best[0]
                candidates=[c for c in hand if c.suit==best[0]]
                # Lead 4th-best or lowest to be uninformative
                candidates.sort(key=lambda c: RANK_ORDER[c.rank])
                lead_idx=max(0, len(candidates)-4) if len(candidates)>=4 else 0
                plan.opening_lead_rank=candidates[lead_idx].rank

        return plan


class CardTracker:
    """Tracks all known card locations for AI decision-making."""
                                                                                                                                                      
    def __init__(self):
                                                                                                                                                            
        self.reset()
                                                                                                                                                      
    def reset(self):
                                                                                                                                                                          
        """Clear all tracked knowledge at the start of a new round."""
                                                                                                                                                            
        self.played=set()                                     
                                                                                                                                                            
        self.my_hand=set()                             
                                                                                                                                                            
        self.my_piles_visible=set()                               
                                                                                                                                                            
        self.opp_piles_visible=set()                                    
                                                                                                                                                            
        self.discarded=set()                                                
                                                                                                                                                            
        self.trick_history=[]                                        
                                                                                                                                                                          
        self.current_trick=[]
                                                                                                                                                            
        self.void_suits=[set(),set()]
        # trump_count_estimate[p]: how many trump cards player p likely holds still
        self.trump_count_estimate=[0, 0]
        # Honor cards (A/K/Q) the human opponent has revealed
        self.honor_played_by_opp=set()   # set of (rank, suit)
        # likely_short[player][suit]: 0.0=unknown, higher=more confident opponent is short
        self.likely_short=[{}, {}]

    def set_hand(self, hand):
        """Register AI hand cards as known-owned cards."""
        self.my_hand={c.id52() for c in hand}

    def init_trump_estimates(self, hand, trump_suit):
        """Seed trump_count_estimate at round start once trump is known.
        AI's own count is exact; opponent's estimated from expected distribution."""
        ai_trump=sum(1 for c in hand if c.suit==trump_suit)
        self.trump_count_estimate[AI_PLAYER]=ai_trump
        # Expect roughly proportional share of remaining trump in opponent hand
        total_trump=13
        known_trump=sum(1 for c in hand if c.suit==trump_suit)
        unknown_trump=max(0, total_trump-known_trump)
        # Opponent holds ~12 unknown cards out of (52-12) unknown pool
        opp_est=round(unknown_trump*12/max(1, 52-12-len(self.played)))
        self.trump_count_estimate[HUMAN]=max(0, min(12, opp_est))

    def card_played(self, card, player):
                                                                                                                                                                          
        """Record card reveal/play event and append to current trick log."""
                                                                                                                                                            
        self.played.add(card.id52())
                                                                                                                                                            
        self.my_hand.discard(card.id52())
                                                                                                                                                            
        self.current_trick.append((card.copy(), player))
                                                                                                                                                      
    def trick_done(self):
        """Commit current trick cards to trick history and update opponent model."""
        if self.current_trick:
            led=self.current_trick[0][0].suit if self.current_trick else None
            if led:
                for c,p in self.current_trick:
                    if c.suit!=led:
                        self.void_suits[p].add(led)
                    # Track trump plays to decrement estimate
                    if hasattr(self, 'trump_count_estimate') and hasattr(self, '_trump_suit_ref'):
                        ts=self._trump_suit_ref
                        if ts and c.suit==ts and 0<=p<2:
                            self.trump_count_estimate[p]=max(0, self.trump_count_estimate[p]-1)
                    # Track honors the opponent has revealed
                    if p==HUMAN and hasattr(self, 'honor_played_by_opp'):
                        if c.rank in ("A","K","Q"):
                            self.honor_played_by_opp.add((c.rank, c.suit))
                    # Update likely_short: if opponent played a low card in suit,
                    # they may have few; ratchet up confidence slightly
                    if p==HUMAN and hasattr(self, 'likely_short') and led:
                        if c.suit==led and c.rank in ("2","3","4","5","6"):
                            cur=self.likely_short[HUMAN].get(led, 0.0)
                            self.likely_short[HUMAN][led]=min(0.8, cur+0.15)
            self.trick_history.append(list(self.current_trick))
        self.current_trick=[]
                                                                                                                                                      
    def set_trump_suit(self, suit):
        """Inform the tracker of the trump suit so trick_done() can update estimates."""
        self._trump_suit_ref=suit

    def opp_trump_estimate(self):
        """Return best estimate of how many trump cards the opponent still holds."""
        return max(0, self.trump_count_estimate[HUMAN])

    def add_virtual_trick(self, cards, winner):
        """Add non-played awarded cards as an initial trick-like history entry."""
                                                                                                                                                                    
        if not cards:
                                                                                                                                                      
            return
                                                                                                                                                                       
        trick=[(c.copy(),winner) for c in cards]
                                                                                                                                                            
        self.trick_history.append(trick)
                                                                                                                                                      
    def update_piles(self, my_piles, opp_piles):
                                                                                                                                                                          
        """Track currently visible top cards from both pile sets."""
                                                                                                                                                            
        self.my_piles_visible=set()
                                                                                                                                                                      
        for pile in my_piles:
                                                                                                                                                                        
            if pile and pile[-1].face_up: self.my_piles_visible.add(pile[-1].id52())
                                                                                                                                                            
        self.opp_piles_visible=set()
                                                                                                                                                                      
        for pile in opp_piles:
                                                                                                                                                                        
            if pile and pile[-1].face_up: self.opp_piles_visible.add(pile[-1].id52())
                                                                                                                                                      
    def set_discarded(self, cards):
                                                                                                                                                            
        self.discarded={c.id52() for c in cards}
                                                                                                                                                                          
        self.played|=self.discarded
                                                                                                                                                      
    def known_ids(self):
                                                                                                                                                                          
        """All card ids that AI knows the location of."""
                                                                                                                                                  
        return self.played | self.my_hand | self.my_piles_visible | self.opp_piles_visible
                                                                                                                                                      
    def unknown_ids(self):
                                                                                                                                                            
        """Cards whose location is unknown (could be in opponent's hand)."""
                                                                                                                                                  
        return ALL_52 - self.known_ids()
    def unknown_by_suit(self):
        """Unknown card ids grouped by suit symbol."""
        out={s:[] for s in SUITS}
        for cid in sorted(self.unknown_ids()):
            c=id_to_card(cid)
            out[c.suit].append(cid)
        return out
    def player_card_probabilities(self, player, hand_size, belief=None, belief_key=None):
        """Approximate per-card probability that `player` currently holds each unknown card."""
        hand_size=max(0, int(hand_size))
        unknown=sorted(self.unknown_ids())
        if hand_size<=0 or not unknown:
            return {}
        probs={cid:0.0 for cid in unknown}
        try:
            player_idx=int(player)
        except Exception:
            player_idx=HUMAN
        player_void=set()
        if 0<=player_idx<len(self.void_suits):
            player_void=set(self.void_suits[player_idx])
        support=[cid for cid in unknown if id_to_card(cid).suit not in player_void]
        if len(support)<hand_size:
            support=list(unknown)
        if not support:
            return probs
        weights=np.ones(len(support), dtype=np.float64)
        if belief_key is not None and belief and isinstance(belief, dict) and str(belief_key) in belief:
            key=str(belief_key)
            arr=np.asarray(belief.get(key), dtype=np.float64).reshape(-1)
            if arr.size>=52:
                weights=np.asarray([max(1e-6, float(arr[cid])) for cid in support], dtype=np.float64)
        total_w=float(np.sum(weights))
        if total_w<=1e-12:
            weights=np.ones(len(support), dtype=np.float64)
            total_w=float(len(support))
        target=min(float(hand_size), float(len(support)))
        scale=target/total_w if total_w>1e-12 else 0.0
        for cid,w in zip(support, weights):
            probs[cid]=max(0.0, min(1.0, float(w*scale)))
        return probs
    def opponent_card_probabilities(self, opp_hand_size, belief=None):
        """Convenience view of unknown-card probabilities for the human opponent."""
        return self.player_card_probabilities(HUMAN, opp_hand_size, belief=belief, belief_key="opp_card_prob")
    def suit_probability_mass(self, card_probs):
        """Expected card-count mass by suit from a card-probability map."""
        out={s:0.0 for s in SUITS}
        for cid,p in (card_probs or {}).items():
            if p<=0.0:
                continue
            out[id_to_card(int(cid)).suit]+=float(p)
        return out
    def belief_summary(self, opp_hand_size):
        """Compact belief diagnostics used by Jarvis analysis panel."""
        by_suit=self.unknown_by_suit()
        void=sorted(self.void_suits[HUMAN])
        return {
            "unknown_total": len(self.unknown_ids()),
            "opp_hand_size": int(max(0, opp_hand_size)),
            "unknown_by_suit": {s: len(v) for s,v in by_suit.items()},
            "opp_void_suits": void,
            "played_count": len(self.played),
        }

    def safe_to_lead_suit(self, suit, trump_suit, hand):
        """Estimate safety of leading this suit as initiative card (0=very risky, 1=safe).

        Considers:
        - Known void (opponent will ruff): very risky
        - We hold the Ace: very safe
        - Ace already played (we hold King): safe
        - likely_short confidence: risky if opponent is short
        - Trump: safe only if we hold many trumps
        """
        if suit is None:
            return 0.5
        if suit == trump_suit:
            tc = sum(1 for c in hand if c.suit == suit)
            return min(1.0, tc / 5.0)
        if suit in self.void_suits[HUMAN]:
            return 0.05  # Opponent KNOWN void — they will ruff
        our_cards = [id_to_card(cid) for cid in self.my_hand if id_to_card(cid).suit == suit]
        has_ace = any(c.rank == 'A' for c in our_cards)
        if has_ace:
            return 0.88
        si = SUITS.index(suit) if suit in SUITS else -1
        if si >= 0:
            ace_id = si * 13 + RANK_ORDER['A']
            if ace_id in self.played:
                has_king = any(c.rank == 'K' for c in our_cards)
                if has_king:
                    return 0.82
        short_conf = self.likely_short[HUMAN].get(suit, 0.0)
        return max(0.08, 0.65 - 0.40 * float(short_conf))

    def inferred_human_void_suits(self):
        """Return frozenset of suits the human is confirmed void in."""
        return frozenset(self.void_suits[HUMAN])

    def inferred_human_suit_mass(self, opp_hand_size, belief=None):
        """Return estimated number of cards human holds per suit as dict {suit: float}."""
        probs = self.opponent_card_probabilities(opp_hand_size, belief=belief)
        mass = {s: 0.0 for s in SUITS}
        for cid, p in probs.items():
            c = id_to_card(int(cid))
            mass[c.suit] += float(p)
        return mass
                                                                                                                                                      
    def possible_opp_hand(self, opp_hand_size):
                                                                                                                                                                          
        """Sample a possible opponent hand from unknown cards."""
                                                                                                                                                                       
        unknown=list(self.unknown_ids())
                                                                                                                                                                    
        if len(unknown)<opp_hand_size: return [id_to_card(i) for i in unknown]
                                                                                                                                                                       
        chosen=random.sample(unknown, opp_hand_size)
                                                                                                                                                  
        return [id_to_card(i) for i in chosen]
                                                                                                                                                      
    def all_tricks(self):
                                                                                                                                                                          
        """Return list of completed tricks for display."""
                                                                                                                                                  
        return self.trick_history
                                                                                                                                                      
    def played_by_suit(self):
                                                                                                                                                                          
        """Return per-suit list of already played cards for side-panel display."""
                                                                                                                                                                       
        out={s:[] for s in SUITS}
                                                                                                                                                                      
        for tid in sorted(self.played):
                                                                                                                                                                           
            c=id_to_card(tid)
                                                                                                                                                                
            out[c.suit].append(c)
                                                                                                                                                  
        return out

                                                                   

                                                                                                                                                  
class SearchState:
                                                                                                                                                                                                                       
    """Lightweight state for minimax search."""
                                                                                                                                                                   
    __slots__=('hands','piles','trick_cards','led_suit','trump','tricks_won',
                                                                                                                                                                                 
               'pts_won','trick_num','leader','phase','bid_winner','bid_amount')
                                                                                                                                                      
    def __init__(self):
                                                                                                                                                                          
        self.hands=[[],[]]; self.piles=[[],[]]; self.trick_cards=[]
                                                                                                                                                                          
        self.led_suit=None; self.trump=None; self.tricks_won=[0,0]
                                                                                                                                                                          
        self.pts_won=[0,0]; self.trick_num=0; self.leader=0
                                                                                                                                                                          
        self.phase=0; self.bid_winner=0; self.bid_amount=0

                                                                                                                                                  
def _make_search_state(game, ai_hand, opp_hand, ai_piles, opp_piles):
                                                                                                                                                                                                                       
    """Clone runtime game data into a compact minimax search state."""
                                                                                                                                                                   
    s=SearchState()
                                                                                                                                                        
    s.hands[AI_PLAYER]=[c.copy() for c in ai_hand]
                                                                                                                                                        
    s.hands[HUMAN]=[c.copy() for c in opp_hand]
                                                                                                                                                        
    s.piles[AI_PLAYER]=[[c.copy() for c in p] for p in ai_piles]
                                                                                                                                                        
    s.piles[HUMAN]=[[c.copy() for c in p] for p in opp_piles]
                                                                                                                                                        
    s.trick_cards=[(c.copy(),p) for c,p in game.trick_cards]
                                                                                                                                                                      
    s.led_suit=game.led_suit; s.trump=game.trump_suit
                                                                                                                                                        
    s.tricks_won=list(game.tricks_won)
                                                                                                                                                        
    s.pts_won=[game.tricks_won[p]*5+card_points(game.cards_won[p]) for p in range(2)]
                                                                                                                                                                      
    s.trick_num=game.trick_num; s.leader=game.trick_leader
                                                                                                                                                                      
    s.bid_winner=game.bid_winner; s.bid_amount=game.bid_amount
                     
                                                                                                                                                                   
    hc=len(s.trick_cards)
                                                                                                                                                                
    if hc==0: s.phase=0                 
                                                                                                                                                  
    elif hc==1: s.phase=1                 
                                                                                                                                                  
    elif hc==2: s.phase=2               
                                                                                                                                                  
    elif hc==3: s.phase=3                 
                                                                                                                                               
    else: s.phase=4                 
                                                                                                                                              
    return s

                                                                                                                                                  
def _get_valid(hand, led_suit):
                                                                                                                                                                      
    """Legal hand-card indices under follow-suit constraints."""
                                                                                                                                                                
    if not led_suit: return list(range(len(hand)))
                                                                                                                                                                   
    m=[i for i,c in enumerate(hand) if c.suit==led_suit]
                                                                                                                                              
    return m if m else list(range(len(hand)))

                                                                                                                                                  
def _get_valid_pile(piles, player, led_suit):
                                                                                                                                                                      
    """Legal pile indices among visible pile tops for a given player."""
                                                                                                                                                                   
    vis=[pi for pi,pile in enumerate(piles[player]) if pile and pile[-1].face_up]
                                                                                                                                                                
    if not vis: return []
                                                                                                                                                                
    if led_suit:
                                                                                                                                                                       
        m=[pi for pi in vis if piles[player][pi][-1].suit==led_suit]
                                                                                                                                                                    
        if m: return m
                                                                                                                                              
    return vis

                                                                                                                                                  
def _estimate_strength(hand, trump):
                                                                                                                                                                      
    """Fast heuristic hand-strength estimate for evaluation/features."""
                                                                                                                                                                   
    s=0.0
                                                                                                                                                                  
    for c in hand:
                                                                                                                                                            
        s+=c.points()*2
                                                                                                                                                                    
        if c.rank=="A": s+=4
                                                                                                                                                      
        elif c.rank=="K": s+=3
                                                                                                                                                      
        elif c.rank=="Q": s+=2
                                                                                                                                                                    
        if c.suit==trump: s+=2
                                                                                                                                              
    return s

                                                                                                                                                  
def _suit_control(hand):
                                                                                                                                                        
    """Estimate suit-control using high cards (A/K/Q/J weighted)."""
                                                                                                                                                                   
    ws={"A":1.0,"K":0.8,"Q":0.55,"J":0.35}
                                                                                                                                                                   
    ctrl={s:0.0 for s in SUITS}
                                                                                                                                                                  
    for c in hand:
                                                                                                                                                            
        ctrl[c.suit]+=ws.get(c.rank,0.0)
                                                                                                                                              
    return ctrl

                                                                                                                                                  
def _trick_win_prob(st):
                                                                                                                                                                      
    """Approximate AI chance to win current trick from visible context."""
                                                                                                                                                                
    if not st.trick_cards:
                                                                                                                                                  
        return 0.5
                                                                                                                                                                   
    ai_best=-1
                                                                                                                                                                   
    opp_best=-1
                                                                                                                                                                   
    led=st.led_suit if st.led_suit else st.trick_cards[0][0].suit
                                                                                                                                                                  
    for c,p in st.trick_cards:
                                                                                                                                                                       
        pw=c.trick_power(led, st.trump)
                                                                                                                                                                    
        if p==AI_PLAYER:
                                                                                                                                                                           
            ai_best=max(ai_best,pw)
                                                                                                                                                   
        else:
                                                                                                                                                                           
            opp_best=max(opp_best,pw)
                                                                                                                                                                
    if ai_best<0:
                                                                                                                                                  
        return 0.2
                                                                                                                                                                
    if opp_best<0:
                                                                                                                                                  
        return 0.8
                                                                                                                                                                   
    d=ai_best-opp_best
                                                                                                                                              
    return 1.0/(1.0+math.exp(-d/5.0))

                                                                                                                                                  
def _soft_choice(values, temperature):
                                                                                                                                                                      
    """Return normalized soft-min probabilities for opponent action weighting."""
                                                                                                                                                                
    if not values:
                                                                                                                                                  
        return []
                                                                                                                                                                   
    m=min(values)
                                                                                                                                                                   
    exps=[math.exp(-(v-m)/max(0.01,temperature)) for v in values]
                                                                                                                                                                   
    s=sum(exps)
                                                                                                                                                                
    if s<=0:
                                                                                                                                                  
        return [1.0/len(values)]*len(values)
                                                                                                                                              
    return [e/s for e in exps]

                                                                                                                                                  
def _pending_pile_players(st):
                                                                                                                                                                      
    """Players that can still be forced to play a pile card in this trick."""
                                                                                                                                                                
    if st.phase<=1:
                                                                                                                                                  
        return (AI_PLAYER, HUMAN)
                                                                                                                                                                
    if st.phase==2:
                                                                                                                                                  
        return (st.leader, 1-st.leader)
                                                                                                                                                                
    if st.phase==3:
                                                                                                                                                  
        return (1-st.leader,)
                                                                                                                                              
    return ()

                                                                                                                                                  
def _forced_pile_card_cost(st, player):
                                                                                                                                                                      
    """Cost when player is constrained to one visible pile card and that card is expensive."""
                                                                                                                                                                
    if st.trump is None or st.led_suit is None:
                                                                                                                                                  
        return 0.0
                                                                                                                                                                
    if player not in _pending_pile_players(st):
                                                                                                                                                  
        return 0.0
                                                                                                                                                                   
    valid=_get_valid_pile(st.piles, player, st.led_suit)
                                                                                                                                                                
    if len(valid)!=1:
                                                                                                                                                  
        return 0.0
                                                                                                                                                                   
    pile=st.piles[player][valid[0]]
                                                                                                                                                                
    if not pile or not pile[-1].face_up:
                                                                                                                                                  
        return 0.0
                                                                                                                                                                   
    card=pile[-1]
                                                                                                                                                                   
    r=RANK_ORDER[card.rank]
                                                                                                                                                                   
    score=0.0
                                                                                                                                                                
    if card.suit==st.trump:
                                                                                                                                                                          
        score+=6.0 + r*1.2
                                                                                                                                                                    
        if st.led_suit==st.trump:
                                                                                                                                                                              
            score+=4.0
                                                                                                                                               
    else:
                                                                                                                                                                          
        score+=max(0.0, r-9)*0.8
                                                                                                                                                                      
    score+=card.points()*1.2
                                                                                                                                                                   
    pot_points=sum(c.points() for c,_ in st.trick_cards)
                                                                                                                                                                      
    score+=max(0.0, 8-pot_points)*0.4
                                                                                                                                              
    return score

                                                                                                                                                  
def _pile_lock_pressure(st):
                                                                                                                                                                      
    """AI-positive when human is more likely to be forced into expensive pile play."""
                                                                                                                                              
    return _forced_pile_card_cost(st, HUMAN)-_forced_pile_card_cost(st, AI_PLAYER)

                                                                                                                                                  
def _void_ruff_continuation_bonus(base, child, actor, played):
                                                                                                                                                                      
    """Actor-centric tactical bonus for ruffing when void in led suit as hand follower."""
                                                                                                   
    if base.phase!=1 or base.trump is None or base.led_suit is None or base.led_suit==base.trump:
        return 0.0
    hand_before=base.hands[actor]
    if any(c.suit==base.led_suit for c in hand_before):
        return 0.0
    trump_cards=[c for c in hand_before if c.suit==base.trump]
    if not trump_cards:
        return 0.0
    best_pre=max((c.trick_power(base.led_suit, base.trump) for c,_ in base.trick_cards), default=-1)
    winning_trumps=[c for c in trump_cards if c.trick_power(base.led_suit, base.trump)>best_pre]
    if not winning_trumps:
        return 0.0
    pot_points=sum(c.points() for c,_ in base.trick_cards)
    if played.suit!=base.trump:
                                                                                            
        slip_penalty=10.0+pot_points*1.1
        if played.points()>0:
            slip_penalty+=played.points()*1.5
        return -slip_penalty
    if played.trick_power(base.led_suit, base.trump)<=best_pre:
        return -4.0
    bonus=12.0+pot_points*1.2
                                                                           
    bonus+=max(0.0, 6.0-RANK_ORDER[played.rank])*0.9
    opp=1-actor
    opp_valid=_get_valid_pile(child.piles, opp, child.led_suit)
    if opp_valid:
        opp_forced_led=all(
            child.piles[opp][pi] and child.piles[opp][pi][-1].face_up and child.piles[opp][pi][-1].suit==child.led_suit
            for pi in opp_valid
        )
        if opp_forced_led:
            bonus+=6.0
            my_valid=_get_valid_pile(child.piles, actor, child.led_suit)
            if my_valid:
                own_cash=max(
                    (child.piles[actor][pi][-1].points()
                     for pi in my_valid
                     if child.piles[actor][pi] and child.piles[actor][pi][-1].face_up),
                    default=0
                )
                bonus+=own_cash*2.4
    return bonus

                                                                                                                                                  
def _value_features(st):
                                                                                                                                                                      
    """Build value-net feature vector from a `SearchState`."""
                                                                                                                                                                   
    f=np.zeros(10,dtype=np.float64)
                                                                                                                                                                   
    cur_ai=st.pts_won[AI_PLAYER]; cur_hu=st.pts_won[HUMAN]
                                                                                                                                                                   
    rem=max(0, TOTAL_PTS-(cur_ai+cur_hu))
                                                                                                                                                                      
    f[0]=cur_ai/165.0; f[1]=cur_hu/165.0
                                                                                                                                                                      
    f[2]=rem/165.0
                                                                                                                                                                      
    f[3]=st.tricks_won[AI_PLAYER]/13.0; f[4]=st.tricks_won[HUMAN]/13.0
                                                                                                                                                                      
    f[5]=1.0 if st.bid_winner==AI_PLAYER else 0.0
                                                                                                                                                                      
    f[6]=st.bid_amount/165.0
                                                                                                                                                        
    f[7]=_estimate_strength(st.hands[AI_PLAYER], st.trump)/120.0
                                                                                                                                                        
    f[8]=_estimate_strength(st.hands[HUMAN], st.trump)/120.0
                                                                                                                                                        
    f[9]=len(st.hands[AI_PLAYER])/12.0
                                                                                                                                              
    return f

                                                                                                                                                                                                          
def _evaluate_state(st, value_net=None, tracker=None):
                                                                                                                                                                      
    """Projected dollar differential from AI's perspective."""
                                                                                                                                                                   
    ai=AI_PLAYER; hu=HUMAN
                                                                                                                                                                   
    cur_ai=st.pts_won[ai]; cur_hu=st.pts_won[hu]
                                                                                                                                                                   
    rem=max(0, TOTAL_PTS-(cur_ai+cur_hu))
                                                                                                                                                                   
    sa=_estimate_strength(st.hands[ai], st.trump)
                                                                                                                                                                   
    sh=_estimate_strength(st.hands[hu], st.trump)
                                                                                                                                                                
    if sa+sh>0:
                                                                                                                                                                       
        exp_ai=rem*(sa/(sa+sh))
                                                                                                                                               
    else:
                                                                                                                                                                       
        exp_ai=rem*0.5
                                                                                                                                                                   
    proj_ai=cur_ai+exp_ai
                                                                                                                                                                   
    proj_hu=cur_hu+(rem-exp_ai)
                                                                                                                                                                
    if st.bid_winner==ai:
                                                                                                                                                                    
        if proj_ai>=st.bid_amount:
                                                                                                                                                                           
            delta_ai=proj_ai; delta_hu=proj_hu
                                                                                                                                                   
        else:
                                                                                                                                                                           
            delta_ai=-st.bid_amount; delta_hu=proj_hu
                                                                                                                                               
    else:
                                                                                                                                                                    
        if proj_hu>=st.bid_amount:
                                                                                                                                                                           
            delta_ai=proj_ai; delta_hu=proj_hu
                                                                                                                                                   
        else:
                                                                                                                                                                           
            delta_ai=proj_ai; delta_hu=-st.bid_amount
                                                                                                                                                                   
    delta=(delta_ai-delta_hu)                                                 
                                                                                                                                                        
    delta+=(st.tricks_won[ai]-st.tricks_won[hu])*2

                                        
                                                                                                                                                        
    delta+=(_trick_win_prob(st)-0.5)*24.0

                                                    
                                                                                                                                                                   
    ai_ctrl=_suit_control(st.hands[ai]); hu_ctrl=_suit_control(st.hands[hu])
                                                                                                                                                        
    delta+=sum((ai_ctrl[s]-hu_ctrl[s]) for s in SUITS)*4.0

                                                                                      
                                                                                                                                                        
    delta+=_pile_lock_pressure(st)*1.8

                                                 
                                                                                                                                                                
    if tracker is not None and hasattr(tracker, "void_suits"):
                                                                                                                                                            
        delta+=len(tracker.void_suits[HUMAN])*3.0
                                                                                                                                                            
        delta-=len(tracker.void_suits[AI_PLAYER])*2.0

                                                                                                                                                                                                                        
    if value_net is not None:
                                                                                                                                                                                                                               
        v=value_net.predict(_value_features(st))
                                                                                                                                                                       
        delta=delta*0.7+v*30.0
                                                                                                                                              
    return delta

                                                                       
                                                                                                                                                               
_node_count=0
                                                                            
                                                                                                                                                               
_max_nodes=max(1, (MAX_SEARCH_MB * 1024 * 1024) // 400)

                                                                                                                                                                                                                                                                                                                                                         
def expectiminimax(st, depth, alpha, beta, deadline, value_net=None, tracker=None):
                                                                                                                                                                                                                                                                                                                               
    """Expectiminimax with alpha-beta for AI nodes and soft-opponent expectation."""
                                                                                                                                              
    global _node_count
                                                                                                                                                                      
    _node_count+=1
    if (_node_count & 1023)==0:
        pressure,_=_memory_pressure()
        if pressure>=2:
            return _evaluate_state(st, value_net, tracker)
                                                                                                                                                                
    if _node_count>_max_nodes or _time.monotonic()>deadline:
                                                                                                                                                                                                          
        return _evaluate_state(st, value_net, tracker)
                                                                                                                                                                
    if depth<=0 or st.trick_num>12:
                                                                                                                                                                                                          
        return _evaluate_state(st, value_net, tracker)

                                                                       
                                                                                                                                                                
    if st.phase>=4 or (st.phase>=2 and not any(st.piles[st.leader])
                                                                                                                                                                            
                        and not any(st.piles[1-st.leader])):
                                                                                                                                                                       
        best=-1; winner=0
                                                                                                                                                                      
        for card,pl in st.trick_cards:
                                                                                                                                                                           
            pw=card.trick_power(st.led_suit,st.trump)
                                                                                                                                                                        
            if pw>best: best=pw; winner=pl
                                                                                                                                                                      
        for card,_ in st.trick_cards:
                                                                                                                                                                
            st.pts_won[winner]+=card.points()
                                                                                                                                                                          
        st.tricks_won[winner]+=1; st.pts_won[winner]+=5
                                                                                                                                                                          
        st.trick_num+=1; st.leader=winner
                                                                                                                                                                          
        st.trick_cards=[]; st.led_suit=None; st.phase=0
                                                                                                                                                                                                                            
        if st.trick_num>12: return _evaluate_state(st, value_net, tracker)
                                                                                                                                                                                                                                                                                                                                                         
        return expectiminimax(st,depth-1,alpha,beta,deadline,value_net,tracker)

                                                                                                                                                                
    if st.phase<2:
                                                                 
                                                                                                                                                                       
        player=st.leader if st.phase==0 else 1-st.leader
                                                                                                                                                                       
        is_max=player==AI_PLAYER
                                                                                                                                                                       
        hand=st.hands[player]
                                                                                                                                                                    
        if not hand:
                                                                                                                                                                              
            st.phase=2
                                                                                                                                                                                                                                                                                                                                                             
            return expectiminimax(st,depth,alpha,beta,deadline,value_net,tracker)
                                                                                                                                                                       
        valid=_get_valid(hand,st.led_suit)
                                                                                                                                                                    
        if not valid:
                                                                                                                                                                              
            st.phase+=1
                                                                                                                                                                        
            if st.phase==2:
                                                                                                                                                                              
                for p in range(2):
                                                                                                                                                                                  
                    for pile in st.piles[p]:
                                                                                                                                                                                    
                        if pile and not pile[-1].face_up: pile[-1].face_up=True
                                                                                                                                                                                                                                                                                                                                                             
            return expectiminimax(st,depth,alpha,beta,deadline,value_net,tracker)
                                                                                                                                                                       
        best_val=-9999 if is_max else 9999
                                                                                                                                                                       
        opp_vals=[]
                                                                                                                                                                      
        for idx in valid:
                                                                                                                                                                           
            child=copy.deepcopy(st)
                                                                                                                                                                           
            card=child.hands[player].pop(idx)
                                                                                                                                                                        
            if not child.led_suit: child.led_suit=card.suit
                                                                                                                                                                
            child.trick_cards.append((card,player))
                                                                                                                                                                              
            child.phase+=1
                                                                                                                                                                        
            if child.phase==2:
                                                                                                                                                                              
                for p in range(2):
                                                                                                                                                                                  
                    for pile in child.piles[p]:
                                                                                                                                                                                    
                        if pile and not pile[-1].face_up: pile[-1].face_up=True
                                                                                                                                                                                                                                                                                                                                                                                  
            v=expectiminimax(child,depth,alpha,beta,deadline,value_net,tracker)
                                                                                                                                                                        
            if is_max:
                                                                                                                                                                                                                                                   
                best_val=max(best_val,v); alpha=max(alpha,v)
                                                                                                                                                       
            else:
                                                                                                                                                                    
                opp_vals.append(v)
                                                                                                                                                                                                                                                   
                best_val=min(best_val,v); beta=min(beta,v)
                                                                                                                                                                                                                                            
            if beta<=alpha: break
                                                                                                                                                                    
        if not is_max and opp_vals:
                                                                                                                                                                           
            probs=_soft_choice(opp_vals, EXPECTI_TEMP)
                                                                                                                                                                           
            best_val=sum(v*p for v,p in zip(opp_vals, probs))
                                                                                                                                                  
        return best_val
                                                                                                                                               
    else:
                                                                               
                                                                                                                                                                       
        player=st.leader if st.phase==2 else 1-st.leader
                                                                                                                                                                       
        is_max=player==AI_PLAYER
                                                                                                                                                                       
        valid=_get_valid_pile(st.piles,player,st.led_suit)
                                                                                                                                                                    
        if not valid:
                                                                                                                                                                        
            if st.phase==2:
                                                                                                                                                                               
                other=1-st.leader
                                                                                                                                                                            
                if any(st.piles[other]):
                                                                                                                                                                                      
                    st.phase=3
                                                                                                                                                                                                                                                                                                                                                                     
                    return expectiminimax(st,depth,alpha,beta,deadline,value_net,tracker)
                                                                                                                                                           
                else:
                                                                                                                                                                                      
                    st.phase=4
                                                                                                                                                                                                                                                                                                                                                                     
                    return expectiminimax(st,depth,alpha,beta,deadline,value_net,tracker)
                                                                                                                                                       
            else:
                                                                                                                                                                                  
                st.phase=4
                                                                                                                                                                                                                                                                                                                                                                 
                return expectiminimax(st,depth,alpha,beta,deadline,value_net,tracker)
                                                                                                                                                                       
        best_val=-9999 if is_max else 9999
                                                                                                                                                                       
        opp_vals=[]
                                                                                                                                                                      
        for pi in valid:
                                                                                                                                                                           
            child=copy.deepcopy(st)
                                                                                                                                                                           
            card=child.piles[player][pi].pop()
                                                                                                                                                                
            child.trick_cards.append((card,player))
                                                                                                                                                                        
            if child.piles[player][pi] and not child.piles[player][pi][-1].face_up:
                                                                                                                                                                                  
                child.piles[player][pi][-1].face_up=True
                                                                                                                                                                              
            child.phase+=1
                                                                                                                                                                        
            if child.phase==3 and not any(child.piles[1-child.leader]):
                                                                                                                                                                                  
                child.phase=4
                                                                                                                                                                                                                                                                                                                                                                                  
            v=expectiminimax(child,depth,alpha,beta,deadline,value_net,tracker)
                                                                                                                                                                        
            if is_max:
                                                                                                                                                                                                                                                   
                best_val=max(best_val,v); alpha=max(alpha,v)
                                                                                                                                                       
            else:
                                                                                                                                                                    
                opp_vals.append(v)
                                                                                                                                                                                                                                                   
                best_val=min(best_val,v); beta=min(beta,v)
                                                                                                                                                                                                                                            
            if beta<=alpha: break
                                                                                                                                                                    
        if not is_max and opp_vals:
                                                                                                                                                                           
            probs=_soft_choice(opp_vals, EXPECTI_TEMP)
                                                                                                                                                                           
            best_val=sum(v*p for v,p in zip(opp_vals, probs))
                                                                                                                                                  
        return best_val

                                                                                                                                                                                                                                                                                                           
def minimax(st, depth, alpha, beta, deadline, value_net=None, tracker=None):
                                                                                                                                                                                                                                                                     
    """Compatibility wrapper around expectiminimax."""
                                                                                                                                                                                                                                                                                                                                                     
    return expectiminimax(st, depth, alpha, beta, deadline, value_net, tracker)

                                                                   

                                                                                                                                                  
class ShelemAI:
                                                                           
                                                                                                                                                                   
    N_PLAY=28
                                                                          
                                                                                                                                                                   
    N_BID=24
                                                                            
                                                                                                                                                                   
    N_VALUE=10
                                                                         
                                                                                                                                                                                                                               
    BG_MC_SAMPLES=64
    BG_IDLE_SLEEP_S=0.015
    FG_ACTION_SLICE_MIN_S=0.015
    BID_ACTIONS=tuple(range(MIN_BID, MAX_BID+5, 5))
    CARD_PLANES=5                                          
    TRICK_SLOT_FEATS=6
    GLOBAL_FEATS=20
    SHARED_INPUT_DIM=52*CARD_PLANES + 4*TRICK_SLOT_FEATS + GLOBAL_FEATS
    BELIEF_EXTRA_DIM=52+4+8
                                                                                                                                                      
    def __init__(self):
                                                                                                                                                                          
        """Initialize hybrid belief/policy-value transformer and AI state."""
        self.shared_net=HybridJarvisModel(
            state_dim=self.SHARED_INPUT_DIM,
            bid_dim=len(self.BID_ACTIONS),
            hand_dim=12,
            pile_dim=4,
            lr=SHARED_NET_LR,
        )
        self.shared_net.load(SHARED_MODEL)
                                                                                                      
        self.value_net=None
        self.epsilon=max(0.02, 0.20-self.shared_net.train_steps*0.00002)
        self.match_examples=[]
        self._current_game=None
                                                                                                                                                                          
        self.round_decisions=[]
                                                                                                                                                                          
        self.round_bid_feat=None; self.round_bid_amount=0
                                                                                                                                                                          
        self.games_played=max(0, self.shared_net.train_steps//64)
                                                                                                                                                            
        self.tracker=CardTracker()
        self.round_plan=None          # RoundPlan built at round start
        self.human_profile=HumanProfile()   # loaded from game history

        self._bg_result=None; self._bg_lock=threading.Lock()
                                                                                                                                                            
        self._bg_stop=threading.Event()
        self._fg_search_active=threading.Event()
                                                                                                                                                                          
        self._bg_state=None
                                                                                                                                                                          
        self._bg_key=None
                                                                                                                                                                          
        self.last_analysis=[]
                                                                                                                                                                          
        self.last_pv=[]
        self.last_tactics=[]
        self.tactics=TacticRegistry()
        self._register_default_tactics()
                                                                                                                                                            
        self._bg_thread=threading.Thread(target=self._background_loop, daemon=True)
                                                                                                                                                            
        self._bg_thread.start()

                                                                                                                                                      
    def save(self):
                                                                                                                                                                                                                                          
        """Persist all learned model checkpoints."""
                                                                                                                                                            
        self.shared_net.save(SHARED_MODEL)
    def observe_game(self, game):
        """Store latest full game context for state encoding in all action heads."""
        self._current_game=game

    def _runtime_search_profile(self, mode="fg"):
        """Memory-aware runtime tuning profile for search-heavy paths."""
        pressure,rss_mb=_memory_pressure()
        profile={
            "pressure": pressure,
            "rss_mb": rss_mb,
            "allow_bg": True,
            "depth_delta": 0,
            "sample_cap": MC_SAMPLES,
            "budget_scale": 1.0,
        }
        if pressure>=2:
            profile.update({
                "allow_bg": False,
                "depth_delta": -2,
                "sample_cap": max(10, MC_SAMPLES//4),
                "budget_scale": 0.45,
            })
        elif pressure>=1:
            profile.update({
                "allow_bg": True,
                "depth_delta": -1,
                "sample_cap": max(16, MC_SAMPLES//2),
                "budget_scale": 0.70,
            })
        if mode=="bg":
            profile["sample_cap"]=max(8, min(self.BG_MC_SAMPLES, int(profile["sample_cap"])))
            if pressure>=1:
                profile["sample_cap"]=max(8, profile["sample_cap"]//2)
            if pressure>=2:
                profile["allow_bg"]=False
        return profile
                                                                                                                                                      
    def shutdown(self):
                                                                                                                                                                          
        """Stop background search worker thread."""
                                                                                                                                                            
        self._bg_stop.set()
                                                                                                                                                                    
        if self._bg_thread.is_alive():
                                                                                                                                                                
            self._bg_thread.join(timeout=0.2)

                                                                                                                                                      
    def new_round(self, hand):
        """Reset per-round analysis/training state and tracker knowledge."""
        self.tracker.reset(); self.tracker.set_hand(hand)
        self.round_plan=None   # will be built after trump selection
        self.round_decisions=[]; self._bg_result=None; self._bg_state=None; self._bg_key=None
        self.last_analysis=[("...",0.0,0.0,0.0,0.0)]; self.last_pv=["analysis pending"]
        self.last_tactics=[]

    def build_round_plan(self, hand, trump_suit, bid_amount, is_bidder, game):
        """Build a RoundPlan after trump is known and hand is final.

        Call this once per round, right after trump selection / discard.
        Also seeds the trump estimate in the CardTracker.
        """
        self.tracker.set_trump_suit(trump_suit)
        self.tracker.init_trump_estimates(hand, trump_suit)
        self.round_plan=RoundPlan.build(
            hand, trump_suit, bid_amount, is_bidder, game, self.tracker
        )
        return self.round_plan

    def _assess_game_posture(self, game):
        """Return the current game posture string (uses round_plan if available)."""
        if self.round_plan is not None:
            return self.round_plan.posture
        ai_score=int(game.scores[AI_PLAYER])
        hu_score=int(game.scores[HUMAN])
        gap=ai_score-hu_score
        if gap>=300:
            return RoundPlan.POSTURE_DEFENDING
        if gap<=-200:
            return RoundPlan.POSTURE_ATTACKING
        return RoundPlan.POSTURE_NORMAL

    def register_tactic(self, name, callback, weight=1.0):
        """Public extension point for adding tactic heuristics at runtime."""
        self.tactics.register(name, callback, weight=weight)

    def _register_default_tactics(self):
        """Named tactics mined from Jarvis deviations and wired as pluggable rules."""
        def _general_ev_upgrade(ctx):
            card=ctx["card"]
            if card.points()==0:
                return (0.8, "baseline low-risk EV bias")
            return (-0.3, "baseline value-card caution")

        def _void_ruff_conversion(ctx):
            if ctx["kind"]!="hand" or ctx["game"].state!=State.PLAY_HAND_FOLLOWER:
                return 0.0
            led=ctx["game"].led_suit
            trump=ctx["game"].trump_suit
            card=ctx["card"]
            valid=ctx["valid_cards"]
            if led is None or trump is None:
                return 0.0
            if any(c.suit==led for c in valid):
                return 0.0
            best_pre=max((c.trick_power(led, trump) for c,_ in ctx["game"].trick_cards), default=-1)
            winning_trump=card.suit==trump and card.trick_power(led, trump)>best_pre
            if winning_trump:
                return (12.0, "void+ruff capture")
            if card.suit!=trump:
                return (-14.0, "slough while ruff available")
            return 0.0

        def _high_pot_conversion(ctx):
            if ctx["kind"]!="hand" or ctx["game"].state!=State.PLAY_HAND_FOLLOWER:
                return 0.0
            led=ctx["game"].led_suit
            trump=ctx["game"].trump_suit
            card=ctx["card"]
            pot=sum(c.points() for c,_ in ctx["game"].trick_cards)
            if pot<10 or led is None or trump is None:
                return 0.0
            best_pre=max((c.trick_power(led, trump) for c,_ in ctx["game"].trick_cards), default=-1)
            if card.trick_power(led, trump)>best_pre:
                return (10.0, "take high pot now")
            return (-10.0, "high pot left to opponent")

        def _minimum_winning_card(ctx):
            if ctx["kind"]!="hand" or ctx["game"].state!=State.PLAY_HAND_FOLLOWER:
                return 0.0
            led=ctx["game"].led_suit
            trump=ctx["game"].trump_suit
            card=ctx["card"]
            valid=ctx["valid_cards"]
            if led is None or trump is None:
                return 0.0
            best_pre=max((c.trick_power(led, trump) for c,_ in ctx["game"].trick_cards), default=-1)
            winners=[c for c in valid if c.trick_power(led, trump)>best_pre]
            if not winners:
                return 0.0
            low=min(winners, key=lambda c: c.trick_power(led, trump))
            if card.rank==low.rank and card.suit==low.suit:
                return (7.0, "lowest winning card")
            if card.trick_power(led, trump)>low.trick_power(led, trump):
                return (-6.0, "overtrump/overwin")
            return 0.0

        def _point_card_protection(ctx):
            if ctx["kind"]!="hand" or ctx["game"].state!=State.PLAY_HAND_FOLLOWER:
                return 0.0
            led=ctx["game"].led_suit
            trump=ctx["game"].trump_suit
            card=ctx["card"]
            if led is None or trump is None:
                return 0.0
            best_pre=max((c.trick_power(led, trump) for c,_ in ctx["game"].trick_cards), default=-1)
            winning=card.trick_power(led, trump)>best_pre
            if (not winning) and card.points()>0:
                return (-9.0, "dumped value card on losing line")
            return 0.0

        def _trump_conservation(ctx):
            card=ctx["card"]
            trump=ctx["game"].trump_suit
            if trump is None or card.suit!=trump:
                return 0.0
            valid=ctx["valid_cards"]
            pot=sum(c.points() for c,_ in ctx["game"].trick_cards)
            non_trump=any(c.suit!=trump for c in valid)
            if non_trump and pot<=5:
                return (-7.0, "spent trump on low-value trick")
            return 0.0

        def _trump_drain_lead(ctx):
            if ctx["kind"]!="hand" or ctx["game"].state!=State.PLAY_HAND_LEADER:
                return 0.0
            card=ctx["card"]
            trump=ctx["game"].trump_suit
            if trump is None:
                return 0.0
            if card.suit!=trump:
                return 0.0
            opp_trump_known=any(
                (cid//13)==SUITS.index(trump)
                for cid in self.tracker.unknown_ids()
            )
            return (6.0, "lead trump to drain") if opp_trump_known else 0.0

        def _bidder_safety_first(ctx):
            g=ctx["game"]
            if int(g.bid_winner)!=AI_PLAYER:
                return 0.0
            need=max(0, int(g.bid_amount)-int(g.live_pts(AI_PLAYER)))
            remain=max(1, TOTAL_PTS-(int(g.live_pts(AI_PLAYER))+int(g.live_pts(HUMAN))))
            pressure=float(need)/float(remain)
            led=g.led_suit
            trump=g.trump_suit
            card=ctx["card"]
            if pressure<0.45 or led is None or trump is None:
                return 0.0
            if g.state==State.PLAY_HAND_FOLLOWER and g.trick_cards:
                best_pre=max((c.trick_power(led, trump) for c,_ in g.trick_cards), default=-1)
                wins=card.trick_power(led, trump)>best_pre
                return (8.0, "contract pressure secure trick") if wins else (-8.0, "contract pressure missed trick")
            return 0.0

        def _endgame_forcing_line(ctx):
            g=ctx["game"]
            if len(g.hands[AI_PLAYER])>2:
                return 0.0
            card=ctx["card"]
            led=g.led_suit
            trump=g.trump_suit
            if led is None or trump is None:
                return 0.0
            valid=ctx["valid_cards"]
            best=max(valid, key=lambda c: c.trick_power(led, trump))
            if card.rank==best.rank and card.suit==best.suit:
                return (5.0, "endgame forcing control")
            return 0.0

        def _contract_breakpoint_strike(ctx):
            g=ctx["game"]
            actor=ctx.get("actor", AI_PLAYER)
            if actor!=AI_PLAYER:
                return 0.0
            if g.bid_winner!=HUMAN:
                return 0.0
            if g.state not in (State.PLAY_HAND_FOLLOWER, State.PLAY_PILE_FOLLOWER):
                return 0.0
            if not g.trick_cards:
                return 0.0
            led=g.led_suit
            trump=g.trump_suit
            if led is None or trump is None:
                return 0.0
            pot=sum(c.points() for c,_ in g.trick_cards)
            if pot<10:
                return 0.0
            card=ctx["card"]
            valid=ctx["valid_cards"]
            best_pre=max((c.trick_power(led, trump) for c,_ in g.trick_cards), default=-1)
            winners=[c for c in valid if c.trick_power(led, trump)>best_pre]
            if not winners:
                return 0.0
            low=min(winners, key=lambda c:c.trick_power(led, trump))
            if card.trick_power(led, trump)<=best_pre:
                return (-15.0, "high pot left unbroken")
            if card.rank==low.rank and card.suit==low.suit:
                return (13.0, "contract breakpoint strike")
            return (-5.0, "high-pot overcommit")

        def _trump_denial_squeeze(ctx):
            g=ctx["game"]
            actor=ctx.get("actor", AI_PLAYER)
            if actor!=AI_PLAYER:
                return 0.0
            if g.bid_winner!=HUMAN:
                return 0.0
            if ctx["kind"]!="hand" or g.state!=State.PLAY_HAND_LEADER:
                return 0.0
            trump=g.trump_suit
            if trump is None:
                return 0.0
            valid=ctx["valid_cards"]
            if not any(c.suit==trump for c in valid):
                return 0.0
            card=ctx["card"]
            opp_has_trump=any(c.suit==trump for c in g.hands[HUMAN])
            if not opp_has_trump:
                opp_has_trump=any((pile and pile[-1].suit==trump) for pile in g.piles[HUMAN])
            if not opp_has_trump:
                return 0.0
            if card.suit==trump:
                return (11.0, "trump denial squeeze")
            return (-8.0, "defensive tempo drift")

        def _value_leak_block(ctx):
            g=ctx["game"]
            actor=ctx.get("actor", AI_PLAYER)
            if actor!=AI_PLAYER:
                return 0.0
            if g.bid_winner!=HUMAN:
                return 0.0
            if g.state not in (State.PLAY_HAND_FOLLOWER, State.PLAY_PILE_FOLLOWER):
                return 0.0
            if not g.trick_cards:
                return 0.0
            led=g.led_suit
            trump=g.trump_suit
            if led is None or trump is None:
                return 0.0
            valid=ctx["valid_cards"]
            card=ctx["card"]
            best_pre=max((c.trick_power(led, trump) for c,_ in g.trick_cards), default=-1)
            winners=[c for c in valid if c.trick_power(led, trump)>best_pre]
            if winners:
                return 0.0
            point_alts=any(c.points()>0 for c in valid)
            if card.points()==0 and point_alts:
                return (9.0, "value leak block")
            if card.points()>0 and any(c.points()==0 for c in valid):
                return (-9.0, "value leak")
            return 0.0

        self.tactics.register("General EV Upgrade", _general_ev_upgrade, weight=1.0)
        self.tactics.register("Void Ruff Conversion", _void_ruff_conversion, weight=1.0)
        self.tactics.register("High-Pot Conversion", _high_pot_conversion, weight=1.0)
        self.tactics.register("Minimum Winning Card", _minimum_winning_card, weight=1.0)
        self.tactics.register("Point Card Protection", _point_card_protection, weight=1.0)
        self.tactics.register("Trump Conservation", _trump_conservation, weight=1.0)
        self.tactics.register("Trump Drain Lead", _trump_drain_lead, weight=1.0)
        self.tactics.register("Bidder Safety First", _bidder_safety_first, weight=1.0)
        self.tactics.register("Endgame Forcing Line", _endgame_forcing_line, weight=1.0)
        self.tactics.register("Contract Breakpoint Strike", _contract_breakpoint_strike, weight=1.0)
        self.tactics.register("Trump Denial Squeeze", _trump_denial_squeeze, weight=1.0)
        self.tactics.register("Value Leak Block", _value_leak_block, weight=1.0)

        # ── New tactics (round-plan aware) ──────────────────────────────────

        def _trump_draw_lead(ctx):
            """Bidder with 6+ trump should open by leading trump to exhaust opponent."""
            g=ctx["game"]
            if ctx["kind"]!="hand" or g.state!=State.PLAY_HAND_LEADER:
                return 0.0
            if int(g.bid_winner)!=AI_PLAYER:
                return 0.0
            trump=g.trump_suit
            card=ctx["card"]
            if trump is None or card.suit!=trump:
                return 0.0
            hand=g.hands[AI_PLAYER]
            my_trump=sum(1 for c in hand if c.suit==trump)
            if my_trump<5:
                return 0.0
            plan=getattr(self, 'round_plan', None)
            if plan and "draw_trump" in plan.phase_goals:
                return (9.0, "trump draw lead — plan phase goal")
            if my_trump>=6:
                return (6.0, "lead trump to exhaust opponent")
            return 0.0

        def _suit_establishment_lead(ctx):
            """Leader with 4+ in a non-trump suit holding A or K should lead to establish it."""
            g=ctx["game"]
            if ctx["kind"]!="hand" or g.state!=State.PLAY_HAND_LEADER:
                return 0.0
            trump=g.trump_suit
            card=ctx["card"]
            if trump is None or card.suit==trump:
                return 0.0
            plan=getattr(self, 'round_plan', None)
            if plan and card.suit in plan.suits_to_establish:
                if card.rank in ("A","K"):
                    return (8.0, "establish suit — plan target")
                return (4.0, "develop suit length")
            hand=g.hands[AI_PLAYER]
            suit_cnt=sum(1 for c in hand if c.suit==card.suit)
            if suit_cnt>=4 and card.rank in ("A","K"):
                return (5.0, "establish long suit with honor")
            return 0.0

        def _honor_guard(ctx):
            """Avoid leading a K/Q into a suit where opponent likely holds the Ace."""
            g=ctx["game"]
            if ctx["kind"]!="hand" or g.state!=State.PLAY_HAND_LEADER:
                return 0.0
            card=ctx["card"]
            if card.rank not in ("K","Q"):
                return 0.0
            plan=getattr(self, 'round_plan', None)
            if plan and (card.suit, card.rank) in plan.honor_guards:
                return (-8.0, "honor guard — opponent likely holds higher")
            # Fallback: check belief — if opponent hasn't shown Ace in this suit,
            # they probably still have it; penalise leading K/Q into it
            opp_honors=getattr(self.tracker, 'honor_played_by_opp', set())
            if ("A", card.suit) not in opp_honors:
                return (-5.0, "Ace not yet shown — guard K/Q")
            return 0.0

        def _void_exploitation_lead(ctx):
            """When leader has a confirmed void and holds low trump, lead the void suit
            so the next trick becomes a ruff opportunity."""
            g=ctx["game"]
            if ctx["kind"]!="hand" or g.state!=State.PLAY_HAND_LEADER:
                return 0.0
            trump=g.trump_suit
            card=ctx["card"]
            if trump is None or card.suit==trump:
                return 0.0
            hand=g.hands[AI_PLAYER]
            my_trump=sum(1 for c in hand if c.suit==trump)
            if my_trump<1:
                return 0.0
            # Check if Jarvis is void in the card's suit but has low trump (ruff potential)
            suit_cards=[c for c in hand if c.suit==card.suit]
            if suit_cards:
                return 0.0   # not void — doesn't apply
            # Actually when void, the game will have already forced us to ruff or slough.
            # Instead reward leading a suit where opponent is known void (forces them to trump)
            opp_void=self.tracker.void_suits[HUMAN]
            if card.suit in opp_void and my_trump>=2:
                return (-6.0, "lead into opp void wastes initiative")
            # Reward leading a suit where WE are shortest (strip our own side suits first)
            suit_len={s: sum(1 for c in hand if c.suit==s) for s in SUITS if s!=trump}
            if suit_len and card.suit==min(suit_len, key=suit_len.get) and suit_len[card.suit]<=2:
                return (5.0, "lead short suit to prepare void ruff")
            return 0.0

        def _late_trump_coup(ctx):
            """Endgame (trick 9+): if opponent has ~1 trump left and Jarvis holds side winners,
            lead trump to strip opponent's last trump before cashing."""
            g=ctx["game"]
            if ctx["kind"]!="hand" or g.state!=State.PLAY_HAND_LEADER:
                return 0.0
            if g.trick_num<9:
                return 0.0
            trump=g.trump_suit
            card=ctx["card"]
            if trump is None or card.suit!=trump:
                return 0.0
            opp_est=self.tracker.opp_trump_estimate() if hasattr(self.tracker,'opp_trump_estimate') else 1
            if opp_est>2:
                return 0.0   # too many trumps left — not a coup situation
            hand=g.hands[AI_PLAYER]
            side_winners=sum(
                1 for c in hand
                if c.suit!=trump and c.rank=="A"
            )
            if side_winners>=1 and opp_est<=1:
                return (10.0, "late trump coup — strip last trump before cashing Aces")
            return 0.0

        self.tactics.register("Trump Draw Lead", _trump_draw_lead, weight=1.0)
        self.tactics.register("Suit Establishment Lead", _suit_establishment_lead, weight=1.0)
        self.tactics.register("Honor Guard", _honor_guard, weight=1.0)
        self.tactics.register("Void Exploitation Lead", _void_exploitation_lead, weight=1.0)
        self.tactics.register("Late Trump Coup", _late_trump_coup, weight=1.0)

    def _belief_context(self, game):
        suit_of=lambda cid: cid//13
        return {
            "unknown_ids": set(self.tracker.unknown_ids()),
            "opp_piles_visible": set(self.tracker.opp_piles_visible),
            "opp_void_suits": {SUITS.index(s) for s in self.tracker.void_suits[HUMAN] if s in SUITS},
            "opp_hand_size": max(0, len(game.hands[HUMAN])),
            "suit_of_id": suit_of,
        }
    def _opponent_play_model(self, game, actor, belief=None):
        """Build probabilistic model for the current opponent hand."""
        opp=1-int(actor)
        if opp not in (0, 1):
            opp=HUMAN
        try:
            opp_hand_size=max(0, len(game.hands[opp]))
        except Exception:
            opp_hand_size=0
        belief_key="opp_card_prob" if opp==HUMAN else None
        card_probs=self.tracker.player_card_probabilities(
            opp,
            opp_hand_size,
            belief=belief,
            belief_key=belief_key,
        )
        void_suits=set()
        if hasattr(self.tracker, "void_suits") and 0<=opp<len(self.tracker.void_suits):
            void_suits=set(self.tracker.void_suits[opp])
        return {
            "opponent": opp,
            "opp_hand_size": opp_hand_size,
            "card_probs": card_probs,
            "suit_mass": self.tracker.suit_probability_mass(card_probs),
            "void_suits": void_suits,
        }
    def _opponent_can_hold(self, opp_model, predicate):
        """Probability opponent holds at least one card matching predicate."""
        if not opp_model:
            return 0.0
        card_probs=opp_model.get("card_probs", {})
        if not card_probs:
            return 0.0
        p_none=1.0
        for cid,p in card_probs.items():
            if p<=0.0:
                continue
            try:
                c=id_to_card(int(cid))
            except Exception:
                continue
            if not predicate(c):
                continue
            pp=max(0.0, min(1.0, float(p)))
            p_none*=1.0-pp
            if p_none<=1e-9:
                return 1.0
        return max(0.0, min(1.0, 1.0-p_none))
    def _initiative_pressure_scale(self, game, actor):
        """Scale initiative bonus by current contract pressure."""
        bidder=int(game.bid_winner) if game.bid_winner in (0, 1) else None
        if bidder is None:
            return 1.0
        try:
            actor_live=float(game.live_pts(actor))
            opp_live=float(game.live_pts(1-actor))
        except Exception:
            return 1.0
        remain=max(1.0, float(TOTAL_PTS)-(actor_live+opp_live))
        if actor==bidder:
            need=max(0.0, float(game.bid_amount)-actor_live)
            return 1.0+0.45*min(1.0, need/remain)
        bust_target=max(0.0, float(TOTAL_PTS)-float(game.bid_amount))
        need=max(0.0, bust_target-actor_live)
        return 1.0+0.35*min(1.0, need/remain)
    def _visible_pile_tops(self, game, player):
        """Return currently visible pile-top cards for one player."""
        out=[]
        try:
            piles=game.piles[player]
        except Exception:
            return out
        for pile in piles:
            if pile and pile[-1].face_up:
                out.append(pile[-1])
        return out
    def _lead_pile_ruff_trap_risk(self, game, actor, lead_card):
        """Risk score for leading non-trump into likely opponent pile-trump overruff."""
        if actor not in (0, 1):
            return 0.0
        trump=game.trump_suit
        if trump is None or lead_card is None or lead_card.suit==trump:
            return 0.0
        opp=1-actor
        opp_tops=self._visible_pile_tops(game, opp)
        if not opp_tops:
            return 0.0
        opp_trumps=[c for c in opp_tops if c.suit==trump]
        if not opp_trumps:
            return 0.0
        opp_has_led=any(c.suit==lead_card.suit for c in opp_tops)
        risk=14.0 if not opp_has_led else 4.0
        if lead_card.points()>0:
            risk+=9.0
        if RANK_ORDER.get(lead_card.rank, 0)>=11:
            risk+=3.0
        my_tops=self._visible_pile_tops(game, actor)
        my_trumps=[c for c in my_tops if c.suit==trump]
        if my_trumps:
            my_best=max(my_trumps, key=lambda c: RANK_ORDER[c.rank])
            opp_best=max(opp_trumps, key=lambda c: RANK_ORDER[c.rank])
            if RANK_ORDER[my_best.rank]>=RANK_ORDER[opp_best.rank]:
                risk-=4.0
            else:
                risk+=4.0
        else:
            risk+=4.0
        return max(0.0, float(risk))
    def _knowledge_play_bonus(self, game, actor, kind, card, valid_cards, opp_model):
        """Initiative-first tactical bias based on explicit opponent card probabilities."""
        if actor not in (0, 1):
            return 0.0
        bonus=0.0
        trump=game.trump_suit
        led=game.led_suit
        opp_void=opp_model.get("void_suits", set()) if isinstance(opp_model, dict) else set()
        valid_cards=[c for c in (valid_cards or []) if c is not None]
        if kind=="hand" and game.state==State.PLAY_HAND_LEADER:
            lead_suit=card.suit
            p_follow=self._opponent_can_hold(opp_model, lambda oc: oc.suit==lead_suit)
            p_higher_follow=self._opponent_can_hold(
                opp_model,
                lambda oc: oc.suit==lead_suit and RANK_ORDER[oc.rank]>RANK_ORDER[card.rank],
            )
            p_beat=min(1.0, p_higher_follow)
            if trump and lead_suit!=trump:
                p_has_trump=self._opponent_can_hold(opp_model, lambda oc: oc.suit==trump)
                p_beat=min(1.0, p_beat + max(0.0, 1.0-p_follow)*p_has_trump)
            keep_control=1.0-p_beat
            bonus+=20.0*(keep_control-0.5)
            if card.points()>0:
                bonus+=8.0*(keep_control-0.5)
            if lead_suit in opp_void and lead_suit!=trump:
                bonus+=3.0 if card.points()==0 else -7.0
            if trump in opp_void and lead_suit!=trump and card.points()>0:
                bonus+=4.0
            ruff_risk=self._lead_pile_ruff_trap_risk(game, actor, card)
            if ruff_risk>0.0:
                bonus-=ruff_risk
                if card.points()==0 and RANK_ORDER.get(card.rank, 0)<=4:
                    bonus+=2.0
        elif kind=="hand" and game.state==State.PLAY_HAND_FOLLOWER and game.trick_cards and led is not None:
            best_pre=max((c.trick_power(led, trump) for c,_ in game.trick_cards), default=-1)
            wins_now=card.trick_power(led, trump)>best_pre
            can_win=any(c.trick_power(led, trump)>best_pre for c in valid_cards)
            pot=sum(c.points() for c,_ in game.trick_cards)+card.points()
            if can_win:
                if wins_now:
                    bonus+=14.0+0.55*pot
                else:
                    bonus-=15.0+(5.0 if card.points()>0 else 0.0)
            else:
                if card.points()==0 and any(c.points()>0 for c in valid_cards):
                    bonus+=4.0
                if card.points()>0 and any(c.points()==0 for c in valid_cards):
                    bonus-=7.0
        elif kind=="pile" and game.state==State.PLAY_PILE_LEADER:
            led_suit=led or card.suit
            opp=1-actor
            try:
                opp_valid=game.get_valid_piles(opp)
            except Exception:
                opp_valid=[]
            if opp_valid:
                cur_power=card.trick_power(led_suit, trump)
                can_beat=False
                for pi in opp_valid:
                    if pi<0 or pi>=len(game.piles[opp]) or not game.piles[opp][pi]:
                        continue
                    oc=game.piles[opp][pi][-1]
                    if oc.trick_power(led_suit, trump)>cur_power:
                        can_beat=True
                        break
                if can_beat:
                    bonus-=6.0
                else:
                    bonus+=7.0+(2.0 if card.points()>0 else 0.0)
        elif kind=="pile" and game.state==State.PLAY_PILE_FOLLOWER and game.trick_cards and led is not None:
            best_pre=max((c.trick_power(led, trump) for c,_ in game.trick_cards), default=-1)
            wins_now=card.trick_power(led, trump)>best_pre
            can_win=any(c.trick_power(led, trump)>best_pre for c in valid_cards)
            pot=sum(c.points() for c,_ in game.trick_cards)+card.points()
            if can_win:
                bonus+=(11.0+0.45*pot) if wins_now else -12.0
            else:
                if card.points()==0 and any(c.points()>0 for c in valid_cards):
                    bonus+=3.0
                if card.points()>0 and any(c.points()==0 for c in valid_cards):
                    bonus-=5.0
        bonus*=self._initiative_pressure_scale(game, actor)
        return float(max(-30.0, min(30.0, bonus)))
                                                                                                                                                      
    def _state_key(self, game):
                                                                                                                                                                          
        """Compact state signature used to match background results."""
        def _public_piles_sig(piles):
            sig=[]
            for pile in piles:
                if not pile:
                    sig.append((0, None, None, False))
                    continue
                top=pile[-1]
                if top.face_up:
                    sig.append((len(pile), top.rank, top.suit, True))
                else:
                    sig.append((len(pile), None, None, False))
            return tuple(sig)
                                                                                                                                                  
        return (
                                                                                                                                                                              
            game.state.name, game.trick_num, game.led_suit, game.trump_suit,
                                                                                                                                                                
            game.active_player(), len(game.trick_cards),
                                                                                                                                                                
            tuple((c.rank,c.suit) for c in game.hands[AI_PLAYER]),
                                                                                                                                                                
            _public_piles_sig(game.piles[AI_PLAYER]),
            _public_piles_sig(game.piles[HUMAN]),
                                                                                                                                                                
            tuple((c.rank,c.suit,p) for c,p in game.trick_cards),
                                                                                                                                                                          
        )
    def _bid_idx_from_amount(self, amount):
        try:
            return self.BID_ACTIONS.index(int(amount))
        except Exception:
            return 0
    def _bid_amount_from_idx(self, idx):
        i=max(0, min(len(self.BID_ACTIONS)-1, int(idx)))
        return int(self.BID_ACTIONS[i])
    def _masked_argmax(self, logits, valid_indices):
        if not valid_indices:
            return 0
        best=valid_indices[0]; best_v=-1e18
        for i in valid_indices:
            v=float(logits[i])
            if v>best_v:
                best_v=v; best=i
        return best
    def _round_bid(self, amount):
        return int(round(float(amount)/5.0))*5
    def _opening_bid_heuristic(self, hand):
        _,_,strength=self._eval_hand(hand)
        et=min(13, max(2, int(strength/8)))
        ov=sum(c.points() for c in hand)
        return et*5+ov*0.6+BID_AGGRESSION
    def _bid_contract_cap(self, hand, value_estimate):
        v=float(np.clip(value_estimate, -1.0, 1.0))
        base=self._opening_bid_heuristic(hand)+BID_CAP_BONUS+v*BID_CAP_VALUE_SCALE
        cap=self._round_bid(base)
        return max(MIN_BID, min(MAX_BID, cap))
    def _encode_shared_state(self, game):
        """State tensor with card ownership/visibility, trick slots, and match context."""
        self.tracker.update_piles(game.piles[AI_PLAYER], game.piles[HUMAN])
        known=self.tracker.known_ids()
        vec=np.zeros(self.SHARED_INPUT_DIM, dtype=np.float64)
        for cid in range(52):
            o=cid*self.CARD_PLANES
            vec[o]=1.0 if cid in self.tracker.my_hand else 0.0
            vec[o+1]=1.0 if cid in self.tracker.my_piles_visible else 0.0
            vec[o+2]=1.0 if cid in self.tracker.opp_piles_visible else 0.0
            vec[o+3]=1.0 if cid in self.tracker.played else 0.0
            vec[o+4]=1.0 if cid not in known else 0.0
        off=52*self.CARD_PLANES
        for i in range(4):
            s=off+i*self.TRICK_SLOT_FEATS
            if i<len(game.trick_cards):
                c,p=game.trick_cards[i]
                vec[s]=RANK_ORDER[c.rank]/12.0
                vec[s+1]=SUITS.index(c.suit)/3.0
                vec[s+2]=1.0 if p==AI_PLAYER else 0.0
                vec[s+3]=1.0 if p==HUMAN else 0.0
                vec[s+4]=c.points()/10.0
                vec[s+5]=1.0 if c.suit==game.trump_suit else 0.0
        g0=off+4*self.TRICK_SLOT_FEATS
        vec[g0+0]=len(game.trick_cards)/4.0
        vec[g0+1]=game.trick_num/12.0
        vec[g0+2]=game.bid_amount/165.0
        vec[g0+3]=1.0 if game.bid_winner==AI_PLAYER else 0.0
        vec[g0+4]=1.0 if game.bid_winner==HUMAN else 0.0
        vec[g0+5]=1.0 if game.trick_leader==AI_PLAYER else 0.0
        vec[g0+6]=1.0 if game.active_player()==AI_PLAYER else 0.0
        vec[g0+7]=game.tricks_won[AI_PLAYER]/13.0
        vec[g0+8]=game.tricks_won[HUMAN]/13.0
        vec[g0+9]=card_points(game.cards_won[AI_PLAYER])/100.0
        vec[g0+10]=card_points(game.cards_won[HUMAN])/100.0
        vec[g0+11]=game.scores[AI_PLAYER]/max(1.0, float(game.match_target))
        vec[g0+12]=game.scores[HUMAN]/max(1.0, float(game.match_target))
        vec[g0+13]=game.round_num/30.0
        vec[g0+14]=game.current_bid/165.0
        vec[g0+15]=game.clock.rem[AI_PLAYER]/max(1.0, game.clock.initial[AI_PLAYER])
        vec[g0+16]=game.clock.rem[HUMAN]/max(1.0, game.clock.initial[HUMAN])
        t=game.trump_suit
        if t in SUITS:
            si=SUITS.index(t)
            vec[g0+17]=si/3.0
        vec[g0+18]=game.state.value/float(len(State)+1)
        vec[g0+19]=1.0 if game.state in (State.BIDDING, State.TAKE_SPECIAL, State.DISCARDING, State.TRUMP_SELECT) else 0.0
        return vec
    def _record_match_example(self, state_vec, head, action_idx):
        if state_vec is None:
            return
        self.match_examples.append((np.asarray(state_vec, dtype=np.float32).copy(), str(head), int(action_idx)))
        if len(self.match_examples)>4096:
            del self.match_examples[:-4096]
                                                                                                                                                      
    def sync_background(self, game):
                                                                                                                                                                          
        """Publish latest game snapshot for continuous background search."""
                                                                                                                                                                       
        trump=getattr(game, "trump_suit", None)
        active=game.active_player()
        play_state=game.state in (
            State.PLAY_HAND_LEADER, State.PLAY_HAND_FOLLOWER,
            State.PLAY_PILE_LEADER, State.PLAY_PILE_FOLLOWER
        )
        profile=self._runtime_search_profile(mode="bg")
                                                                                                                                                                    
        if (not profile["allow_bg"]) or trump is None or not play_state or (active!=AI_PLAYER and not SHOW_HUMAN_MOVE_ANALYSIS):
                                                                                                                                                             
            with self._bg_lock:
                                                                                                                                                                                  
                self._bg_state=None
                                                                                                                                                                                  
                self._bg_key=None
            if play_state and active!=AI_PLAYER and not SHOW_HUMAN_MOVE_ANALYSIS:
                self.last_analysis=[("Hidden Opponent Turn",0.0,0.0,0.0,0.0)]
                self.last_pv=["Jarvis does not use your exact hand cards for live analysis."]
                                                                                                                                                      
            return
                                                                                                                                                         
        with self._bg_lock:
                                                                                                                                                                
            self._bg_state=copy.deepcopy(game)
                                                                                                                                                                
            self._bg_key=self._state_key(game)
                                                                                                                                                      
    def _background_loop(self):
                                                                                                                                                                          
        """Continuously search current round state in background."""
                                                                                                                                          
        while not self._bg_stop.is_set():
                                                                                                                                                             
            with self._bg_lock:
                                                                                                                                                                               
                gs=self._bg_state
                                                                                                                                                                               
                gk=self._bg_key
                                                                                                                                                                        
            if gs is None:
                                                                                                                                                                    
                _time.sleep(self.BG_IDLE_SLEEP_S)
                                                                                                                                                               
                continue
            if self._fg_search_active.is_set():
                _time.sleep(self.BG_IDLE_SLEEP_S)
                                                                                                                                                               
                continue
            profile=self._runtime_search_profile(mode="bg")
            if not profile["allow_bg"]:
                _time.sleep(self.BG_IDLE_SLEEP_S*2)
                continue
                                                                                                                                                                           
            deadline=_time.monotonic()+BG_SEARCH_SLICE_S
                                                                                                                                           
            try:
                depth=max(2, BG_TREE_DEPTH+int(profile["depth_delta"]))
                bg_samples=max(8, min(self.BG_MC_SAMPLES, int(profile["sample_cap"])))
                                                                                                                                                                                                                                           
                ranked, pv=self._rank_from_game_state(gs, deadline, depth, bg_samples, mode="bg")
                                                                                                                                                                               
                traces=[]
                                                                                                                                                                               
                tops=ranked[:3]
                                                                                                                                                                            
                if tops and profile["pressure"]==0:
                                                                                                                                                                                   
                    t_deadline=_time.monotonic()+BG_SEARCH_SLICE_S*1.2
                                                                                                                                                                     
                    with ThreadPoolExecutor(max_workers=min(2, len(tops))) as ex:
                                                                                                                                                                                       
                        futs={ex.submit(self._trace_tree_for_action, gs, r, depth, t_deadline):i for i,r in enumerate(tops)}
                                                                                                                                                                                       
                        ordered=[None]*len(tops)
                                                                                                                                                                                      
                        for f in as_completed(futs):
                                                                                                                                                           
                            try:
                                                                                                                                                                                    
                                ordered[futs[f]]=f.result()
                                                                                                                                                                              
                            except Exception:
                                                                                                                                                                                    
                                pass
                                                                                                                                                                                   
                    traces=[t for t in ordered if t]
                                                                                                                                                              
            except Exception:
                                                                                                                                                                    
                _time.sleep(self.BG_IDLE_SLEEP_S)
                                                                                                                                                               
                continue
                                                                                                                                                                           
            analysis=[]
                                                                                                                                                                          
            for r in ranked[:5]:
                                                                                                                                                                               
                lbl=r["label"]
                                                                                                                                                                    
                analysis.append((lbl, r.get("display_ev", r["ev"]), r["prob"], r["samples"], r["nodes"]))
                                                                                                                                                             
            with self._bg_lock:
                                                                                                                                                                                  
                self._bg_result={
                                                                                                                                                                                      
                    "key": gk,
                                                                                                                                                                                      
                    "analysis": analysis,
                                                                                                                                                                                      
                    "pv": (traces[:4]+pv[:8]) if traces else pv[:12],
                                                                                                                                                                                      
                    "ranked": ranked,
                                                                                                                                                                                  
                }
                                                                                                                                                                    
                self.last_analysis=analysis if analysis else [("...",0.0,0.0,0.0,0.0)]
                                                                                                                                                                    
                self.last_pv=((traces[:4]+pv[:8]) if traces else pv[:12]) if (traces or pv) else ["analysis pending"]
            _time.sleep(self.BG_IDLE_SLEEP_S)

                                                                                                                                                      
    def _sample_hidden_state(self, game, opp_hand_size, belief=None):
                                                                                                                                                                                                                                      
        """Sample hidden cards from unknown ids for Monte Carlo search."""
        self.tracker.update_piles(game.piles[AI_PLAYER], game.piles[HUMAN])
                                                                                                                                                                       
        known=self.tracker.known_ids()
                                                                                                                                                                       
        unknown=list(ALL_52-known)
        ai_hidden=sum(1 for pile in game.piles[AI_PLAYER] for card in pile if not card.face_up)
        opp_hidden=sum(1 for pile in game.piles[HUMAN] for card in pile if not card.face_up)
        need=opp_hand_size+ai_hidden+opp_hidden
        if need<=0:
            return [], [[c.copy() for c in p] for p in game.piles[AI_PLAYER]], [[c.copy() for c in p] for p in game.piles[HUMAN]]
        if not unknown:
            pool=random.choices(tuple(ALL_52), k=need)
            opp_ids=pool[:opp_hand_size]
            hidden_ids=pool[opp_hand_size:]
        else:
            opp_prob=self.tracker.opponent_card_probabilities(opp_hand_size, belief=belief)
            opp_candidates=[cid for cid in unknown if opp_prob.get(cid, 0.0)>0.0]
            if len(opp_candidates)<opp_hand_size:
                opp_candidates=list(unknown)
            base_weights=np.asarray([max(1e-6, float(opp_prob.get(cid, 1.0))) for cid in opp_candidates], dtype=np.float64)
            opp_ids=weighted_sample_without_replacement(opp_candidates, base_weights, opp_hand_size)
            rem=[cid for cid in unknown if cid not in set(opp_ids)]
            hidden_need=ai_hidden+opp_hidden
            if len(rem)>=hidden_need:
                hidden_ids=random.sample(rem, hidden_need)
            elif rem:
                hidden_ids=list(rem)+random.choices(rem, k=hidden_need-len(rem))
            else:
                hidden_ids=random.choices(unknown, k=hidden_need)
        ai_hidden_ids=hidden_ids[:ai_hidden]
        opp_hidden_ids=hidden_ids[ai_hidden:]
        opp_hand=[id_to_card(i) for i in opp_ids]

        def _build_piles(src_piles, sampled_ids):
            out=[]; idx=0
            for pile in src_piles:
                new_pile=[]
                for card in pile:
                    if card.face_up:
                        new_pile.append(card.copy())
                    else:
                        if idx<len(sampled_ids):
                            nc=id_to_card(sampled_ids[idx]); idx+=1
                        elif unknown:
                            nc=id_to_card(random.choice(unknown))
                        else:
                            nc=card.copy()
                        nc.face_up=False
                        new_pile.append(nc)
                out.append(new_pile)
            return out

        ai_piles=_build_piles(game.piles[AI_PLAYER], ai_hidden_ids)
        opp_piles=_build_piles(game.piles[HUMAN], opp_hidden_ids)
        return opp_hand, ai_piles, opp_piles

                                                                                                                                                      
    def _best_response_label(self, hand, game, idx, depth, n_samples, deadline):
                                                                                                                                                                          
        """Estimate most likely opponent hand response label for PV display."""
                                                                                                                                                                       
        opp_hand_size=len(game.hands[HUMAN])
        belief=self.shared_net.infer(self._encode_shared_state(game), context=self._belief_context(game)).get("belief")
                                                                                                                                                                       
        scores={}
                                                                                                                                                                       
        counts={}
                                                                                                                                                                      
        for _ in range(n_samples):
                                                                                                                                                                        
            if _time.monotonic()>deadline: break
                                                                                                                                                                           
            opp_hand, ai_piles, opp_piles=self._sample_hidden_state(game, opp_hand_size, belief=belief)
                                                                                                                                                                           
            st=_make_search_state(game, hand, opp_hand,
                                                                                                                                                                                                     
                                   ai_piles, opp_piles)
                                                                                                                                                                           
            played=st.hands[AI_PLAYER].pop(idx if idx<len(st.hands[AI_PLAYER]) else 0)
                                                                                                                                                                        
            if not st.led_suit: st.led_suit=played.suit
                                                                                                                                                                
            st.trick_cards.append((played, AI_PLAYER))
                                                                                                                                                                              
            st.phase+=1
                                                                                                                                                                        
            if st.phase==2:
                                                                                                                                                                              
                for p in range(2):
                                                                                                                                                                                  
                    for pile in st.piles[p]:
                                                                                                                                                                                    
                        if pile and not pile[-1].face_up: pile[-1].face_up=True
                               
                                                                                                                                                                           
            player=st.leader if st.phase==0 else 1-st.leader
                                                                                                                                                                        
            if st.phase<2:
                                                                                                                                                                               
                valid=_get_valid(st.hands[player], st.led_suit)
                                                                                                                                                                            
                if not valid: continue
                                                                                                                                                                               
                best_v=99999; best_card=None
                                                                                                                                                                              
                for ridx in valid:
                                                                                                                                                                                   
                    child=copy.deepcopy(st)
                                                                                                                                                                                   
                    card=child.hands[player].pop(ridx)
                                                                                                                                                                                
                    if not child.led_suit: child.led_suit=card.suit
                                                                                                                                                                        
                    child.trick_cards.append((card,player))
                                                                                                                                                                                      
                    child.phase+=1
                                                                                                                                                                                
                    if child.phase==2:
                                                                                                                                                                                      
                        for p in range(2):
                                                                                                                                                                                          
                            for pile in child.piles[p]:
                                                                                                                                                                                            
                                if pile and not pile[-1].face_up: pile[-1].face_up=True
                                                                                                                                                                                                                                                                                  
                    v=minimax(child, max(1,depth-1), -99999, 99999, deadline, self.value_net, self.tracker)
                                                                                                                                                                                
                    if v<best_v: best_v=v; best_card=card
                                                                                                                                                       
            else:
                                                                                                                                                                               
                valid=_get_valid_pile(st.piles, player, st.led_suit)
                                                                                                                                                                            
                if not valid: continue
                                                                                                                                                                               
                best_v=99999; best_card=None
                                                                                                                                                                              
                for pi in valid:
                                                                                                                                                                                   
                    child=copy.deepcopy(st)
                                                                                                                                                                                   
                    card=child.piles[player][pi].pop()
                                                                                                                                                                        
                    child.trick_cards.append((card,player))
                                                                                                                                                                                
                    if child.piles[player][pi] and not child.piles[player][pi][-1].face_up:
                                                                                                                                                                                          
                        child.piles[player][pi][-1].face_up=True
                                                                                                                                                                                      
                    child.phase+=1
                                                                                                                                                                                
                    if child.phase==3 and not any(child.piles[1-child.leader]):
                                                                                                                                                                                          
                        child.phase=4
                                                                                                                                                                                                                                                                                  
                    v=minimax(child, max(1,depth-1), -99999, 99999, deadline, self.value_net, self.tracker)
                                                                                                                                                                                
                    if v<best_v: best_v=v; best_card=card
                                                                                                                                                                        
            if best_card is None: continue
                                                                                                                                                                           
            lbl=f"{best_card.rank}{best_card.suit}"
                                                                                                                                                                
            scores[lbl]=scores.get(lbl,0.0)+best_v
                                                                                                                                                                
            counts[lbl]=counts.get(lbl,0)+1
                                                                                                                                                                    
        if not scores: return None
                                                                                                                                                                       
        best=min(scores.items(), key=lambda kv: kv[1]/max(1,counts.get(kv[0],1)))
                                                                                                                                                  
        return best[0]

                                                                                                                                                      
    def _best_pile_response_label(self, game, st, depth, n_samples, deadline):
                                                                                                                                                                          
        """Estimate likely opponent pile response label for PV display."""
                                                                                                                                                                       
        scores={}
                                                                                                                                                                       
        counts={}
                                                                                                                                                                       
        player=HUMAN
                                                                                                                                                                      
        for _ in range(n_samples):
                                                                                                                                                                        
            if _time.monotonic()>deadline: break
                                                                                                                                                                           
            valid=_get_valid_pile(st.piles, player, st.led_suit)
                                                                                                                                                                        
            if not valid: continue
                                                                                                                                                                           
            best_v=99999; best_card=None
                                                                                                                                                                          
            for pi in valid:
                                                                                                                                                                               
                child=copy.deepcopy(st)
                                                                                                                                                                               
                card=child.piles[player][pi].pop()
                                                                                                                                                                    
                child.trick_cards.append((card,player))
                                                                                                                                                                            
                if child.piles[player][pi] and not child.piles[player][pi][-1].face_up:
                                                                                                                                                                                      
                    child.piles[player][pi][-1].face_up=True
                                                                                                                                                                                  
                child.phase+=1
                                                                                                                                                                            
                if child.phase==3 and not any(child.piles[1-child.leader]):
                                                                                                                                                                                      
                    child.phase=4
                                                                                                                                                                                                                                                                              
                v=minimax(child, max(1,depth-1), -99999, 99999, deadline, self.value_net, self.tracker)
                                                                                                                                                                            
                if v<best_v: best_v=v; best_card=card
                                                                                                                                                                        
            if best_card is None: continue
                                                                                                                                                                           
            lbl=f"{best_card.rank}{best_card.suit}"
                                                                                                                                                                
            scores[lbl]=scores.get(lbl,0.0)+best_v
                                                                                                                                                                
            counts[lbl]=counts.get(lbl,0)+1
                                                                                                                                                                    
        if not scores: return None
                                                                                                                                                                       
        best=min(scores.items(), key=lambda kv: kv[1]/max(1,counts.get(kv[0],1)))
                                                                                                                                                  
        return best[0]

                                                                                                                                                      
    def _build_scenario_lines(self, game, hand, best_idx, depth):
                                                                                                                                                                          
        """Build human-readable principal-variation style scenario text."""
                                                                                                                                                                       
        tnum=game.trick_num
                                                                                                                                                                       
        lines=[]
                                                                                                                                                                       
        n_samples=6
                                                                                                                                                                       
        deadline=_time.monotonic()+0.04
                                                                                                                                                                       
        best_card=hand[best_idx]
                                                                                                                                                                       
        opp_label=self._best_response_label(hand, game, best_idx, depth, n_samples, deadline) or "?"
                                                     
                                                                                                                                                                       
        belief=self.shared_net.infer(self._encode_shared_state(game), context=self._belief_context(game)).get("belief")
        opp_hand, ai_piles, opp_piles=self._sample_hidden_state(game, len(game.hands[HUMAN]), belief=belief)
                                                                                                                                                                       
        st=_make_search_state(game, hand, opp_hand, ai_piles, opp_piles)
                           
                                                                                                                                                                       
        j_idx=next((i for i,c in enumerate(st.hands[AI_PLAYER])
                                                                                                                                                                                
                    if c.rank==best_card.rank and c.suit==best_card.suit),0)
                                                                                                                                                                       
        played=st.hands[AI_PLAYER].pop(j_idx)
                                                                                                                                                                    
        if not st.led_suit: st.led_suit=played.suit
                                                                                                                                                            
        st.trick_cards.append((played, AI_PLAYER))
                                                                                                                                                                          
        st.phase+=1
                                          
                                                                                                                                                                       
        y_hand=f"(?) {label_to_ui_text(opp_label)}"
                                                                                                                                                                    
        if st.phase<2:
                                                                                                                                                                           
            valid=_get_valid(st.hands[HUMAN], st.led_suit)
                                                                                                                                                                        
            if valid and opp_label!="?":
                                                                                                                                                                              
                for ridx in valid:
                                                                                                                                                                                   
                    c=st.hands[HUMAN][ridx]
                                                                                                                                                                                
                    if f"{c.rank}{c.suit}"==opp_label:
                                                                                                                                                                                       
                        card=st.hands[HUMAN].pop(ridx)
                                                                                                                                                                            
                        st.trick_cards.append((card,HUMAN))
                                                                                                                                                                                          
                        st.phase+=1
                                                                                                                                           
                        break
                                                                                                                                                                        
            if st.phase==1 and valid:
                                                                                                                                                                               
                card=st.hands[HUMAN].pop(valid[0])
                                                                                                                                                                    
                st.trick_cards.append((card,HUMAN))
                                                                                                                                                                                  
                st.phase+=1
                                     
                                                                                                                                                                    
        if st.phase==2:
                                                                                                                                                                          
            for p in range(2):
                                                                                                                                                                              
                for pile in st.piles[p]:
                                                                                                                                                                                
                    if pile and not pile[-1].face_up: pile[-1].face_up=True
                                             
                                                                                                                                                                       
        j_pile="-"
                                                                                                                                                                       
        valid=_get_valid_pile(st.piles, AI_PLAYER, st.led_suit)
                                                                                                                                                                    
        if valid:
                                                                                                                                                                           
            best_v=-99999; best_pi=valid[0]
                                                                                                                                                                          
            for pi in valid:
                                                                                                                                                                               
                child=copy.deepcopy(st)
                                                                                                                                                                               
                card=child.piles[AI_PLAYER][pi].pop()
                                                                                                                                                                    
                child.trick_cards.append((card,AI_PLAYER))
                                                                                                                                                                            
                if child.piles[AI_PLAYER][pi] and not child.piles[AI_PLAYER][pi][-1].face_up:
                                                                                                                                                                                      
                    child.piles[AI_PLAYER][pi][-1].face_up=True
                                                                                                                                                                                  
                child.phase+=1
                                                                                                                                                                            
                if child.phase==3 and not any(child.piles[1-child.leader]):
                                                                                                                                                                                      
                    child.phase=4
                                                                                                                                                                                                                                                                              
                v=minimax(child, max(1,depth-1), -99999, 99999, deadline, self.value_net, self.tracker)
                                                                                                                                                                            
                if v>best_v: best_v=v; best_pi=pi
                                                                                                                                                                           
            card=st.piles[AI_PLAYER][best_pi].pop()
                                                                                                                                                                
            st.trick_cards.append((card,AI_PLAYER))
                                                                                                                                                                        
            if st.piles[AI_PLAYER][best_pi] and not st.piles[AI_PLAYER][best_pi][-1].face_up:
                                                                                                                                                                                  
                st.piles[AI_PLAYER][best_pi][-1].face_up=True
                                                                                                                                                                              
            st.phase+=1
                                                                                                                                                                           
            j_pile=card_ui_text(card)
                            
                                                                                                                                                                       
        y_pile="(?) ?"
                                                                                                                                                                    
        if st.phase>=3:
                                                                                                                                                                           
            y_lbl=self._best_pile_response_label(game, st, depth, n_samples, deadline) or "?"
                                                                                                                                                                           
            y_pile=f"(?) {label_to_ui_text(y_lbl)}"
                                                                                                                                                                           
            valid=_get_valid_pile(st.piles, HUMAN, st.led_suit)
                                                                                                                                                                        
            if valid and y_lbl!="?":
                                                                                                                                                                              
                for pi in valid:
                                                                                                                                                                                   
                    c=st.piles[HUMAN][pi][-1]
                                                                                                                                                                                
                    if f"{c.rank}{c.suit}"==y_lbl:
                                                                                                                                                                                       
                        card=st.piles[HUMAN][pi].pop()
                                                                                                                                                                            
                        st.trick_cards.append((card,HUMAN))
                                                                                                                                                                                    
                        if st.piles[HUMAN][pi] and not st.piles[HUMAN][pi][-1].face_up:
                                                                                                                                                                                              
                            st.piles[HUMAN][pi][-1].face_up=True
                                                                                                                                                                                          
                        st.phase+=1
                                                                                                                                           
                        break
                                                                                                                                                                        
            if st.phase==3 and valid:
                                                                                                                                                                               
                card=st.piles[HUMAN][valid[0]].pop()
                                                                                                                                                                    
                st.trick_cards.append((card,HUMAN))
                                                                                                                                                                                  
                st.phase+=1
                                                                                                                                                            
        lines.append(f"Trick {tnum}: J(H): {card_ui_text(best_card)}, "
                                                                                                                                                                         
                     f"Y(H): {y_hand}, J(T): {j_pile}, Y(T): {y_pile}")
                                                                       
                                                                                                                                                                    
        if len(st.trick_cards)>=2:
                                                                                                                                                                           
            best=-1; winner=st.leader
                                                                                                                                                                          
            for c,p in st.trick_cards:
                                                                                                                                                                               
                pw=c.trick_power(st.led_suit, st.trump)
                                                                                                                                                                            
                if pw>best:
                                                                                                                                                                                   
                    best=pw; winner=p
                                                                                                                                                                           
            nxt_hand=st.hands[winner]
                                                                                                                                                                        
            if nxt_hand:
                                                                                                                                                                               
                lead=max(nxt_hand, key=lambda c:c.trick_power(c.suit, st.trump))
                                                                                                                                                                               
                who="J" if winner==AI_PLAYER else "Y"
                                                                                                                                                                    
                lines.append(f"Trick {tnum+1} likely lead: {who}(H): {card_ui_text(lead)}")
                                                                                                                                                  
        return lines

                                                               
                                                                                                                                                      
    def _bid_features(self,hand):
                                                                                                                                                            
        """Extract 24-D bid features (must match training script ordering)."""
                                                                                                                                                                       
        f=np.zeros(self.N_BID,dtype=np.float64)
                                                                                                                                                                       
        sc={s:0 for s in SUITS}; hi={s:0.0 for s in SUITS}
                                                                                                                                                                      
        for c in hand:
                                                                                                                                                                              
            sc[c.suit]+=1
                                                                                                                                                                
            hi[c.suit]+=RANK_ORDER[c.rank]+(3 if c.rank=="A" else 2 if c.rank=="K" else 0)
                                                                                                                                                                       
        best=max(SUITS,key=lambda s:(sc[s],hi[s]))
                                                                                                                                                                          
        f[0]=sc[best]/13.0; f[1]=hi[best]/50.0
                                                                                                                                                            
        f[2]=sum(1 for c in hand if c.rank=="A")/4.0
                                                                                                                                                            
        f[3]=sum(1 for c in hand if c.rank=="K")/4.0
                                                                                                                                                            
        f[4]=sum(1 for c in hand if c.rank=="Q")/4.0
                                                                                                                                                            
        f[5]=sum(c.points() for c in hand)/100.0
                                                                                                                                                                       
        voids=sum(1 for s in SUITS if s!=best and sc[s]==0)
                                                                                                                                                                       
        singles=sum(1 for s in SUITS if s!=best and sc[s]==1)
                                                                                                                                                                          
        f[6]=voids/3.0; f[7]=singles/3.0
                                                                                                                                                                      
        for i,s in enumerate(SUITS): f[8+i]=sc[s]/13.0
                                                                                                                                                            
        f[12]=sum(RANK_ORDER[c.rank] for c in hand)/156.0
                                                                                                                                                                       
        ntl=sorted([sc[s] for s in SUITS if s!=best],reverse=True)
                                                                                                                                                                          
        f[13]=ntl[0]/13.0 if ntl else 0
                                                                                                                                                                       
        ak=sum(1 for s in SUITS if any(c.suit==s and c.rank=="A" for c in hand)
                                                                                                                                                                   
               and any(c.suit==s and c.rank=="K" for c in hand))
                                                                                                                                                                          
        f[14]=ak/4.0
                                                                                                                                                            
        f[15]=sum(1 for c in hand if c.rank=="10")/4.0
                                                                                                                                                            
        f[16]=sum(1 for c in hand if c.rank=="5")/4.0
                                                                                                                                                                       
        _,_,strength=self._eval_hand(hand)
                                                                                                                                                            
        f[17]=min(13,max(2,int(strength/8)))/13.0
                                                                                                                                                            
        f[18]=sum(c.points() for c in hand if c.suit==best)/50.0
                                                                                                                                                            
        f[19]=len(hand)/16.0
                                                  
                                                                                                                                                            
        f[20]=sum(1 for c in hand if c.suit!=best and RANK_ORDER[c.rank]>=9)/12.0
                         
                                                                                                                                                            
        f[21]=sum(1 for s in SUITS if s!=best and sc[s]==2)/3.0
                                  
                                                                                                                                                                       
        trump_ranks=[RANK_ORDER[c.rank] for c in hand if c.suit==best]
                                                                                                                                                            
        f[22]=np.mean(trump_ranks)/12.0 if trump_ranks else 0
                                                           
                                                                                                                                                            
        f[23]=sc[best]/len(hand) if hand else 0
                                                                                                                                                  
        return f

                                                               
                                                                                                                                                      
    def _card_features(self,card,hand,game,is_leading):
                                                                                                                                                                          
        """Extract 28-D play features for candidate card evaluation."""
                                                                                                                                                                       
        G=game; f=np.zeros(self.N_PLAY,dtype=np.float64); trump=G.trump_suit
                                                                                                                                                                          
        f[0]=RANK_ORDER[card.rank]/12.0
                                                                                                                                                                          
        f[1]=1.0 if card.suit==trump else 0.0
                                                                                                                                                            
        f[2]=card.points()/10.0
                                                                                                                                                                          
        f[3]=1.0 if is_leading else 0.0
                                                                                                                                                            
        f[4]=(1.0 if card.suit==G.led_suit else 0.0) if G.led_suit else 0.5
                                                                                                                                                                    
        if G.trick_cards:
                                                                                                                                                                           
            bp=max(c.trick_power(G.led_suit,trump) for c,_ in G.trick_cards)
                                                                                                                                                                           
            led=G.led_suit if G.led_suit else card.suit
                                                                                                                                                                
            f[5]=1.0 if card.trick_power(led,trump)>bp else 0.0
                                                                                                                                                                
            f[6]=sum(c.points() for c,_ in G.trick_cards)/30.0
                                                                                                                                                   
        else: f[5]=1.0; f[6]=0.0
                                                                                                                                                                       
        sh={}
                                                                                                                                                                      
        for c in hand: sh[c.suit]=sh.get(c.suit,0)+1
                                                                                                                                                            
        f[7]=sh.get(card.suit,0)/12.0
                                                                                                                                                            
        f[8]=(sh.get(trump,0)/12.0) if trump else 0
                                                                                                                                                            
        f[9]=len(hand)/12.0
                                                                                                                                                                          
        f[10]=G.tricks_won[AI_PLAYER]/13.0; f[11]=G.tricks_won[HUMAN]/13.0
                                                                                                                                                            
        f[12]=card_points(G.cards_won[AI_PLAYER])/100.0
                                                                                                                                                            
        f[13]=card_points(G.cards_won[HUMAN])/100.0
                                                                                                                                                                          
        f[14]=G.trick_num/12.0; f[15]=G.bid_amount/165.0
                                                                                                                                                                          
        f[16]=1.0 if G.bid_winner==AI_PLAYER else 0.0
                                                                                                                                                                       
        mr=RANK_ORDER[card.rank]; ho=0; seen=self.tracker.played|self.tracker.my_hand
                                                                                                                                                                       
        si=SUITS.index(card.suit)
                                                                                                                                                                      
        for ri in range(mr+1,13):
                                                                                                                                                                        
            if si*13+ri not in seen: ho+=1
                                                                                                                                                                          
        f[17]=ho/12.0
                                                                                                                                                                       
        vc=sum(1 for s in SUITS if s!=trump and sh.get(s,0)==0)
                                                                                                                                                                          
        f[18]=vc/3.0
                                                                                                                                                                    
        if G.bid_winner==AI_PLAYER:
                                                                                                                                                                           
            cur=G.tricks_won[AI_PLAYER]*5+card_points(G.cards_won[AI_PLAYER])
                                                                                                                                                                
            f[19]=max(0,G.bid_amount-cur)/165.0
                                                                                                                                                   
        else: f[19]=0.0
                                                                                                                                                            
        f[20]=(G.tricks_won[HUMAN]*5+card_points(G.cards_won[HUMAN]))/165.0
                                                                                                                                                            
        f[21]=len(G.trick_cards)/4.0
                                                                                                                                                            
        f[22]=1.0 if card.rank in("5","10","A") else 0.0
                                                                                                                                                            
        f[23]=1.0 if sh.get(card.suit,1)-1==0 else 0.0
                                                                                                                                                                          
        f[24]=1.0 if RANK_ORDER[card.rank]>=11 else 0.0
                                                                                                                                                                          
        f[25]=1.0 if RANK_ORDER[card.rank]<=4 else 0.0
                                                                                                                                                                          
        f[26]=G.scores[AI_PLAYER]/1000.0
                                                                                                                                                                          
        f[27]=G.scores[HUMAN]/1000.0
                                                                                                                                                  
        return f

                                                                                                                                                      
    def _heuristic_play(self,card,hand,game,is_leading):
                                                                                                                                                                          
        """Rule-based tactical score used as a fast prior over legal plays."""
                                                                                                                                                                       
        G=game; trump=G.trump_suit; score=0.0
                                                                                                                                                                    
        if is_leading:
                                                                                                                                                                        
            if card.suit!=trump:
                                                                                                                                                                            
                if card.rank=="A": score+=30
                                                                                                                                                              
                elif card.rank=="K": score+=22
                                                                                                                                                              
                elif card.rank=="Q": score+=12
                                                                                                                                                              
                elif card.rank in("10","5"):
                                                                                                                                                                                   
                    hh=any(c.suit==card.suit and RANK_ORDER[c.rank]>RANK_ORDER[card.rank]
                                                                                                                                                                                         
                           for c in hand if c is not card)
                                                                                                                                                                                      
                    score+=15 if hh else -5
                                                                                                                                                           
                else: score+=RANK_ORDER[card.rank]*0.5
                                                                                                                                                       
            else:
                                                                                                                                                                               
                sh={}
                                                                                                                                                                              
                for c in hand: sh[c.suit]=sh.get(c.suit,0)+1
                                                                                                                                                                               
                tc=sh.get(trump,0)
                                                                                                                                                                            
                if tc>=4: score+=10+RANK_ORDER[card.rank]
                                                                                                                                                              
                elif card.rank=="A": score+=18
                                                                                                                                                           
                else: score+=RANK_ORDER[card.rank]*0.3-5
                                                                                                                                                                        
            if G.bid_winner==HUMAN:
                                                                                                                                                                               
                opp_have=G.tricks_won[HUMAN]*5+card_points(G.cards_won[HUMAN])
                                                                                                                                                                            
                if opp_have<G.bid_amount*0.5 and G.trick_num>6: score+=5
                                                                                                                                                   
        else:
                                                                                                                                                                           
            led=G.led_suit
                                                                                                                                                                           
            bp=max(c.trick_power(led,trump) for c,_ in G.trick_cards)
                                                                                                                                                                           
            mp=card.trick_power(led,trump)
                                                                                                                                                                           
            tp=sum(c.points() for c,_ in G.trick_cards)+card.points()
                                                                                                                                                                           
            cw=mp>bp
                                                                                                                                                                        
            if card.suit==led:
                                                                                                                                                                            
                if cw: score+=20+tp*0.5; score-=RANK_ORDER[card.rank]*0.3
                                                                                                                                                           
                else:
                                                                                                                                                                        
                    score+=(12-RANK_ORDER[card.rank])*0.5
                                                                                                                                                                                
                    if card.points()>0: score-=card.points()*2
                                                                                                                                                          
            elif card.suit==trump:
                                                                                                                                                                            
                if cw: score+=15+tp*0.4; score-=RANK_ORDER[card.rank]*0.5
                                                                                                                                                           
                else: score-=10
                                                                                                                                                       
            else:
                                                                                                                                                                    
                score+=(12-RANK_ORDER[card.rank])*0.3
                                                                                                                                                                            
                if card.points()>0: score-=card.points()*3
                                                                                                                                                           
                else: score+=5
                                                                                                                                                  
        return score

                                                                                                                                                      
    def _eval_hand(self,hand):
                                                                                                                                                            
        """Return (best_trump, trump_len, heuristic_strength) for bidding logic."""
                                                                                                                                                                       
        sc={s:0 for s in SUITS}; ss={s:0.0 for s in SUITS}
                                                                                                                                                                      
        for c in hand:
                                                                                                                                                                
            sc[c.suit]+=1; ss[c.suit]+=RANK_ORDER[c.rank]+(3 if c.rank=="A" else 0)+(2 if c.rank=="K" else 0)
                                                                                                                                                                       
        bs=max(SUITS,key=lambda s:(sc[s],ss[s])); tl=sc[bs]; st=tl*6
                                                                                                                                                                      
        for c in hand:
                                                                                                                                                                        
            if c.rank=="A": st+=8
                                                                                                                                                          
            elif c.rank=="K": st+=5
                                                                                                                                                          
            elif c.rank=="Q": st+=3
                                                                                                                                                          
            elif c.rank in("J","10"): st+=2
                                                                                                                                                                      
        for s in SUITS:
                                                                                                                                                                        
            if s!=bs and sc[s]==0: st+=6
                                                                                                                                                          
            elif s!=bs and sc[s]==1: st+=3
                                                                                                                                                  
        return bs,tl,st

                                                               
                                                                                                                                                      
    def _time_budget(self, game):
                                                                                                                                                                          
        """Calculate time to spend on this move."""
                                                                                                                                                                       
        rem=game.clock.rem[AI_PLAYER]
                                                                                                                                                                       
        tricks_left=max(1, 12-game.trick_num+1)
                                                                               
        budget=rem*0.62/(tricks_left*2.8)
        if game.trick_num<4:
            max_budget=0.95
        elif game.trick_num<9:
            max_budget=1.35
        else:
            max_budget=2.20
        budget=max(0.08, min(budget, max_budget))
                                                                                                                                                  
        return budget

                                                                                                                                                      
    def _action_label(self, card, player, from_pile=False):
                                                                                                                                                                       
        who="J" if player==AI_PLAYER else "Y"
                                                                                                                                                  
        return f"{who}({'T' if from_pile else 'H'}):{card_ui_text(card)}"

                                                                                                                                                      
    def _rank_from_game_state(self, game, deadline, depth, n_samples, mode="fg"):
                                                                                                                                                                                                                                                                                                                           
        """Rank active-player legal actions by belief-guided IS-MC + expectiminimax."""
        self.tracker.update_piles(game.piles[AI_PLAYER], game.piles[HUMAN])
        hand_phase=game.state in (State.PLAY_HAND_LEADER, State.PLAY_HAND_FOLLOWER)
        actor=game.active_player()
        if actor is None:
            return [], []
        if actor!=AI_PLAYER and not SHOW_HUMAN_MOVE_ANALYSIS:
            return [], []
        view_sign=1.0 if actor==AI_PLAYER else -1.0
        if hand_phase:
            valid=game.get_valid_hand(actor)
            actions=[("hand", idx, game.hands[actor][idx].copy()) for idx in valid]
        else:
            valid=game.get_valid_piles(actor)
            actions=[("pile", pi, game.piles[actor][pi][-1].copy()) for pi in valid]
        if not actions:
            return [], []
        time_left=max(0.0, deadline-_time.monotonic())
        if time_left<=0.0:
            return [], []
        profile=self._runtime_search_profile(mode=mode)
        if mode=="bg" and not profile["allow_bg"]:
            return [], []
        depth=max(1, int(depth)+int(profile["depth_delta"]))
        n_samples=max(6, min(int(n_samples), int(profile["sample_cap"])))

        state_vec=self._encode_shared_state(game)
        net_out=self.shared_net.infer(state_vec, context=self._belief_context(game))
        belief=net_out.get("belief", {})
        prior_logits=net_out["hand_logits"] if hand_phase else net_out["pile_logits"]
        prior_vals=np.asarray([float(prior_logits[a[1]]) for a in actions], dtype=np.float64)
        pri_s=prior_vals-prior_vals.max()
        pri_e=np.exp(pri_s)
        prior_probs=pri_e/(np.sum(pri_e)+1e-9)
        opp_model=self._opponent_play_model(game, actor, belief=belief)

        valid_cards=[a[2] for a in actions]
        tactic_bonus={}
        tactic_hits={}
        knowledge_bonus={}
        for ai,(kind,idx,card) in enumerate(actions):
            ctx={"game": game, "kind": kind, "idx": idx, "card": card, "valid_cards": valid_cards, "actor": actor}
            bonus,hits=self.tactics.score(ctx)
            tactic_bonus[ai]=float(bonus)
            tactic_hits[ai]=hits
            knowledge_bonus[ai]=self._knowledge_play_bonus(game, actor, kind, card, valid_cards, opp_model)

        stats={i:{"total":0.0,"count":0,"best":0.0,"nodes":0,"regret":0.0} for i in range(len(actions))}
        pv_counts={}
        opp_hand_size=len(game.hands[HUMAN])
        action_slice=max(
            self.FG_ACTION_SLICE_MIN_S,
            min(0.045 if mode=="bg" else 0.065, time_left/max(1, len(actions)))
        )
        action_slice=max(self.FG_ACTION_SLICE_MIN_S*0.75, action_slice*float(profile["budget_scale"]))
        global _node_count

        for si in range(n_samples):
            if _time.monotonic()>deadline:
                break
            if (si & 7)==0:
                pressure,_=_memory_pressure()
                if pressure>=2 and mode=="bg":
                    break
            opp_hand, ai_piles, opp_piles=self._sample_hidden_state(game, opp_hand_size, belief=belief)
            base=_make_search_state(game, game.hands[AI_PLAYER], opp_hand, ai_piles, opp_piles)
            base_pressure=_pile_lock_pressure(base)
            sample_rows=[]
            action_order=list(range(len(actions)))
            random.shuffle(action_order)
            for ai in action_order:
                now=_time.monotonic()
                if now>deadline:
                    break
                action_deadline=min(deadline, now+action_slice)
                child=copy.deepcopy(base)
                kind,pos,card=actions[ai]
                if kind=="hand":
                    played=child.hands[actor].pop(pos if pos<len(child.hands[actor]) else 0)
                    if not child.led_suit:
                        child.led_suit=played.suit
                    child.trick_cards.append((played, actor))
                    child.phase+=1
                    if child.phase==2:
                        for p in range(2):
                            for pile in child.piles[p]:
                                if pile and not pile[-1].face_up:
                                    pile[-1].face_up=True
                else:
                    played=child.piles[actor][pos].pop()
                    child.trick_cards.append((played, actor))
                    if child.piles[actor][pos] and not child.piles[actor][pos][-1].face_up:
                        child.piles[actor][pos][-1].face_up=True
                    child.phase+=1
                    if child.phase==3 and not any(child.piles[1-child.leader]):
                        child.phase=4
                _refresh_search_node_budget()
                _node_count=0
                v=minimax(child, depth, -99999, 99999, action_deadline, self.value_net, self.tracker)
                lead_trump_lock=0.0
                if kind=="hand" and not base.led_suit and child.trump and played.suit==child.trump:
                    lead_trump_lock=_forced_pile_card_cost(child, actor)
                if lead_trump_lock>0:
                    v+=(-2.0*lead_trump_lock) if actor==AI_PLAYER else (2.0*lead_trump_lock)
                if kind=="hand":
                    ruff_bias=_void_ruff_continuation_bonus(base, child, actor, played)
                    if ruff_bias:
                        v+=ruff_bias if actor==AI_PLAYER else -ruff_bias
                v+=(_pile_lock_pressure(child)-base_pressure)*1.3
                v+=tactic_bonus.get(ai, 0.0)
                v+=knowledge_bonus.get(ai, 0.0)
                v+=0.05*float(prior_vals[ai])
                label=self._action_label(card, actor, kind=="pile")
                sample_rows.append((ai, v, label))
                stats[ai]["total"]+=v
                stats[ai]["count"]+=1
                stats[ai]["nodes"]+=_node_count
            if not sample_rows:
                continue
            mean_v=sum(row[1] for row in sample_rows)/max(1, len(sample_rows))
            for ai,v,_ in sample_rows:
                stats[ai]["regret"]+=v-mean_v
            if actor==AI_PLAYER:
                bi,_,b_lbl=max(sample_rows, key=lambda row: row[1])
                stats[bi]["best"]+=1.0
                pv_counts[b_lbl]=pv_counts.get(b_lbl,0)+1
            else:
                sample_vals=[row[1] for row in sample_rows]
                probs=_soft_choice(sample_vals, EXPECTI_TEMP)
                for i,p in enumerate(probs):
                    stats[sample_rows[i][0]]["best"]+=p
                bi=max(range(len(probs)), key=lambda i: probs[i])
                pv_counts[sample_rows[bi][2]]=pv_counts.get(sample_rows[bi][2],0)+1

        if not any(s["count"] for s in stats.values()):
            return [], []
        total_best=max(1e-9, sum(s["best"] for s in stats.values()))
        regret_pos=np.asarray([max(0.0, stats[i]["regret"]) for i in range(len(actions))], dtype=np.float64)
        if float(np.sum(regret_pos))<=1e-9:
            regret_probs=np.full(len(actions), 1.0/max(1, len(actions)), dtype=np.float64)
        else:
            regret_probs=regret_pos/(np.sum(regret_pos)+1e-9)

        ranked=[]
        for ai,act in enumerate(actions):
            kind,idx,card=act
            s=stats[ai]
            best_p=float(s["best"]/total_best)
            final_prob=0.50*best_p + 0.25*float(prior_probs[ai]) + 0.25*float(regret_probs[ai])
            avg_ev=s["total"]/max(1, s["count"])
            ranked.append({
                "kind": kind,
                "idx": idx,
                "label": self._action_label(card, actor, kind=="pile"),
                "ev": avg_ev,
                "display_ev": avg_ev*view_sign,
                "prob": final_prob,
                "samples": s["count"],
                "nodes": s["nodes"],
                "tactic_bonus": float(tactic_bonus.get(ai, 0.0)),
                "knowledge_bonus": float(knowledge_bonus.get(ai, 0.0)),
                "tactics": [h.name for h in tactic_hits.get(ai, [])[:3]],
                "regret": float(s["regret"]),
                "prior_prob": float(prior_probs[ai]),
            })
        ranked.sort(key=lambda r:(r["samples"]>0, r["display_ev"], r["prob"]), reverse=True)

        belief_summary=self.tracker.belief_summary(opp_hand_size)
        arch=net_out.get("architecture", {})
        total_nodes=int(sum(r["nodes"] for r in ranked))
        total_samples=max(1, int(sum(r["samples"] for r in ranked)))
        top=ranked[0]
        led_diag=game.led_suit
        p_follow=0.0
        if led_diag in SUITS:
            p_follow=self._opponent_can_hold(opp_model, lambda oc: oc.suit==led_diag)
        p_opp_trump=0.0
        if game.trump_suit in SUITS:
            p_opp_trump=self._opponent_can_hold(opp_model, lambda oc: oc.suit==game.trump_suit)
        self.last_tactics=top.get("tactics", [])
        pv=[
            f"Hybrid model: belief {arch.get('belief_transformer_layers', 6)}L + policy/value {arch.get('policy_value_transformer_layers', 12)}L",
            f"Search: depth={depth} samples={n_samples} evaluated={total_samples} nodes={total_nodes}",
            f"Belief: unseen={belief_summary['unknown_total']} opp_hand={belief_summary['opp_hand_size']} void={','.join(belief_summary['opp_void_suits']) or '-'}",
            f"Opp model: P(follow {led_diag or '-'})={p_follow:.0%} P(trump)={p_opp_trump:.0%}",
            f"Mode: {mode} action-slice={action_slice*1000:.0f}ms",
            "Prob blend: 50% best-share + 25% policy prior + 25% regret-match",
        ]
        if top.get("tactics"):
            pv.append(f"Tactics on top line: {', '.join(top['tactics'])}")
        pv.extend(
            f"{lbl} likely {cnt/total_best:.0%}"
            for lbl,cnt in sorted(pv_counts.items(), key=lambda kv: kv[1], reverse=True)[:6]
        )
        return ranked, pv

                                                                                                                                                      
    def _resolve_if_needed(self, st):
                                                                                                                                                                          
        """Resolve completed trick in search state; return False when round finished."""
                                                                                                                                                                    
        if not (st.phase>=4 or (st.phase>=2 and not any(st.piles[st.leader]) and not any(st.piles[1-st.leader]))):
                                                                                                                                                      
            return True
                                                                                                                                                                       
        best=-1; winner=0
                                                                                                                                                                      
        for card,pl in st.trick_cards:
                                                                                                                                                                           
            pw=card.trick_power(st.led_suit, st.trump)
                                                                                                                                                                        
            if pw>best:
                                                                                                                                                                               
                best=pw; winner=pl
                                                                                                                                                                      
        for card,_ in st.trick_cards:
                                                                                                                                                                
            st.pts_won[winner]+=card.points()
                                                                                                                                                                          
        st.tricks_won[winner]+=1
                                                                                                                                                                          
        st.pts_won[winner]+=5
                                                                                                                                                                          
        st.trick_num+=1
                                                                                                                                                                          
        st.leader=winner
                                                                                                                                                                          
        st.trick_cards=[]
                                                                                                                                                                          
        st.led_suit=None
                                                                                                                                                                          
        st.phase=0
                                                                                                                                                  
        return st.trick_num<=12

                                                                                                                                                      
    def _advance_phase_if_no_moves(self, st):
                                                                                                                                                                          
        """Advance state when current actor has no legal moves."""
                                                                                                                                                                    
        if st.phase<2:
                                                                                                                                                                           
            player=st.leader if st.phase==0 else 1-st.leader
                                                                                                                                                                           
            valid=_get_valid(st.hands[player], st.led_suit)
                                                                                                                                                                        
            if valid:
                                                                                                                                                          
                return True
                                                                                                                                                                              
            st.phase+=1
                                                                                                                                                                        
            if st.phase==2:
                                                                                                                                                                              
                for p in range(2):
                                                                                                                                                                                  
                    for pile in st.piles[p]:
                                                                                                                                                                                    
                        if pile and not pile[-1].face_up:
                                                                                                                                                                                              
                            pile[-1].face_up=True
                                                                                                                                                      
            return False
                                                                                                                                                                       
        player=st.leader if st.phase==2 else 1-st.leader
                                                                                                                                                                       
        valid=_get_valid_pile(st.piles, player, st.led_suit)
                                                                                                                                                                    
        if valid:
                                                                                                                                                      
            return True
                                                                                                                                                                    
        if st.phase==2:
                                                                                                                                                                           
            other=1-st.leader
                                                                                                                                                                
            st.phase=3 if any(st.piles[other]) else 4
                                                                                                                                                   
        else:
                                                                                                                                                                              
            st.phase=4
                                                                                                                                                  
        return False

                                                                                                                                                      
    def _phase_actor_kind(self, st):
                                                                                                                                                            
        """Return (actor, kind) where kind is 'hand' or 'pile'."""
                                                                                                                                                                    
        if st.phase<2:
                                                                                                                                                      
            return (st.leader if st.phase==0 else 1-st.leader), "hand"
                                                                                                                                                  
        return (st.leader if st.phase==2 else 1-st.leader), "pile"

                                                                                                                                                      
    def _apply_action(self, st, actor, kind, idx):
                                                                                                                                                                          
        """Apply chosen action in-place to search state."""
                                                                                                                                                                    
        if kind=="hand":
                                                                                                                                                                           
            card=st.hands[actor].pop(idx)
                                                                                                                                                                        
            if not st.led_suit:
                                                                                                                                                                                  
                st.led_suit=card.suit
                                                                                                                                                                
            st.trick_cards.append((card, actor))
                                                                                                                                                                              
            st.phase+=1
                                                                                                                                                                        
            if st.phase==2:
                                                                                                                                                                              
                for p in range(2):
                                                                                                                                                                                  
                    for pile in st.piles[p]:
                                                                                                                                                                                    
                        if pile and not pile[-1].face_up:
                                                                                                                                                                                              
                            pile[-1].face_up=True
                                                                                                                                                      
            return card
                                                                                                                                                                       
        card=st.piles[actor][idx].pop()
                                                                                                                                                            
        st.trick_cards.append((card, actor))
                                                                                                                                                                    
        if st.piles[actor][idx] and not st.piles[actor][idx][-1].face_up:
                                                                                                                                                                              
            st.piles[actor][idx][-1].face_up=True
                                                                                                                                                                          
        st.phase+=1
                                                                                                                                                                    
        if st.phase==3 and not any(st.piles[1-st.leader]):
                                                                                                                                                                              
            st.phase=4
                                                                                                                                                  
        return card

                                                                                                                                                      
    def _trace_tree_for_action(self, game, ranked_row, depth, deadline):
                                                                                                                                                                          
        """Build one truncated principal line for a ranked root action."""
                                                                                                                                                                       
        belief=self.shared_net.infer(self._encode_shared_state(game), context=self._belief_context(game)).get("belief")
        opp_hand, ai_piles, opp_piles=self._sample_hidden_state(game, len(game.hands[HUMAN]), belief=belief)
                                                                                                                                                                       
        st=_make_search_state(game, game.hands[AI_PLAYER], opp_hand, ai_piles, opp_piles)
                                                                                                                                                                       
        actor=game.active_player()
                                                                                                                                                                    
        if actor is None:
                                                                                                                                                      
            return f"{ranked_row['label']}: no active player"
                                                                                                                                                                       
        card=self._apply_action(st, actor, ranked_row["kind"], ranked_row["idx"])
                                                                                                                                                                       
        seq=[self._action_label(card, actor, ranked_row["kind"]=="pile")]
                                                                                                                                                                       
        plies=0
                                                                                                                                          
        while plies<7 and _time.monotonic()<deadline:
                                                                                                                                                                        
            if not self._resolve_if_needed(st):
                                                                                                                                   
                break
                                                                                                                                                                        
            if not self._advance_phase_if_no_moves(st):
                                                                                                                                                               
                continue
                                                                                                                                                                           
            actor,kind=self._phase_actor_kind(st)
                                                                                                                                                                        
            if kind=="hand":
                                                                                                                                                                               
                valid=_get_valid(st.hands[actor], st.led_suit)
                                                                                                                                                       
            else:
                                                                                                                                                                               
                valid=_get_valid_pile(st.piles, actor, st.led_suit)
                                                                                                                                                                        
            if not valid:
                                                                                                                                   
                break
                                                                                                                                                                           
            best_idx=valid[0]
                                                                                                                                                                           
            best_v=-99999 if actor==AI_PLAYER else 99999
                                                                                                                                                                          
            for idx in valid:
                                                                                                                                                                               
                child=copy.deepcopy(st)
                                                                                                                                                                    
                self._apply_action(child, actor, kind, idx)
                                                                                                                                                                                                                                                                              
                v=minimax(child, max(1,depth-1), -99999, 99999, deadline, self.value_net, self.tracker)
                                                                                                                                                                            
                if actor==AI_PLAYER:
                                                                                                                                                                                
                    if v>best_v:
                                                                                                                                                                                       
                        best_v=v; best_idx=idx
                                                                                                                                                           
                else:
                                                                                                                                                                                
                    if v<best_v:
                                                                                                                                                                                       
                        best_v=v; best_idx=idx
                                                                                                                                                                           
            card=self._apply_action(st, actor, kind, best_idx)
                                                                                                                                                                
            seq.append(self._action_label(card, actor, kind=="pile"))
                                                                                                                                                                              
            plies+=1
                                                                                                                                                  
        return f"{ranked_row['label']} p={ranked_row['prob']:.0%} EV={ranked_row.get('display_ev', ranked_row['ev']):.1f} | {' -> '.join(seq)}"

    def _pick_opening_lead(self, hand, valid, game):
        """Return the best hand index for the first lead of trick 1.

        Uses RoundPlan recommendations plus guard logic.  Falls back to None
        (caller keeps MC-ranked choice) if no strong convention applies.
        """
        if not valid or game.trick_num!=1:
            return None
        trump=game.trump_suit
        plan=self.round_plan

        # ── Lazy plan build if human was bidder (trump known from game state) ──
        if plan is None and trump is not None:
            plan=self.build_round_plan(
                hand, trump, game.bid_amount, game.bid_winner==AI_PLAYER, game
            )

        if plan is None or trump is None:
            return None

        target_suit=plan.opening_lead_suit
        target_rank=plan.opening_lead_rank

        if target_suit is None:
            return None

        # Find card in valid indices matching the plan
        for i in valid:
            c=hand[i]
            if c.suit==target_suit and (target_rank is None or c.rank==target_rank):
                return i

        # Fallback: any valid card in the recommended suit
        for i in valid:
            if hand[i].suit==target_suit:
                return i

        return None

    def _critical_void_trump_override(self, hand, valid, game, chosen_idx):
        """Guardrail: when void in led suit, avoid sloughing if a low winning trump is available."""
        if game.state!=State.PLAY_HAND_FOLLOWER:
            return chosen_idx
        led=game.led_suit
        trump=game.trump_suit
        if led is None or trump is None or led==trump:
            return chosen_idx
        if any(hand[i].suit==led for i in valid):
            return chosen_idx
        best_pre=max((c.trick_power(led, trump) for c,_ in game.trick_cards), default=-1)
        winning_trumps=[i for i in valid if hand[i].suit==trump and hand[i].trick_power(led, trump)>best_pre]
        if not winning_trumps:
            return chosen_idx
        low_winner=min(winning_trumps, key=lambda i:RANK_ORDER[hand[i].rank])
        chosen=hand[chosen_idx]
        chosen_wins=chosen.trick_power(led, trump)>best_pre
        pot_points=sum(c.points() for c,_ in game.trick_cards)
        opp_forced_led=False
        try:
            opp_valid=game.get_valid_piles(HUMAN)
            opp_forced_led=bool(opp_valid) and all(
                game.piles[HUMAN][pi] and game.piles[HUMAN][pi][-1].face_up and game.piles[HUMAN][pi][-1].suit==led
                for pi in opp_valid
            )
        except Exception:
            opp_forced_led=False
        ai_cash=0
        try:
            ai_valid=game.get_valid_piles(AI_PLAYER)
            if ai_valid:
                ai_cash=max(
                    (game.piles[AI_PLAYER][pi][-1].points()
                     for pi in ai_valid
                     if game.piles[AI_PLAYER][pi] and game.piles[AI_PLAYER][pi][-1].face_up),
                    default=0
                )
        except Exception:
            ai_cash=0
        must_ruff=(not chosen_wins) or chosen.suit!=trump
        pressure=(pot_points>0) or opp_forced_led or (ai_cash>=10) or (game.bid_winner==HUMAN)
        if must_ruff and pressure:
            return low_winner
        if chosen_idx in winning_trumps and chosen_idx!=low_winner and (opp_forced_led or ai_cash>=10):
            return low_winner
        return chosen_idx

    def _lead_pile_ruff_trap_override(self, hand, valid, game, chosen_idx):
        """Guardrail: avoid leading high-value non-trumps into obvious pile-trump overruff traps."""
        if game.state!=State.PLAY_HAND_LEADER or len(valid)<=1:
            return chosen_idx
        actor=game.active_player()
        if actor not in (0, 1):
            actor=AI_PLAYER
        chosen_card=hand[chosen_idx]
        chosen_risk=self._lead_pile_ruff_trap_risk(game, actor, chosen_card)
        if chosen_risk<12.0 or chosen_card.suit==game.trump_suit:
            return chosen_idx
        best_idx=chosen_idx
        best_key=(chosen_risk, chosen_card.points(), RANK_ORDER.get(chosen_card.rank, 0))
        for i in valid:
            c=hand[i]
            risk=self._lead_pile_ruff_trap_risk(game, actor, c)
            key=(risk, c.points(), RANK_ORDER.get(c.rank, 0))
            if key<best_key:
                best_key=key
                best_idx=i
        if best_idx==chosen_idx:
            return chosen_idx
        best_risk=best_key[0]
        if (best_risk+6.0<=chosen_risk) or (chosen_card.points()>0 and best_risk<chosen_risk):
            return best_idx
        return chosen_idx

    def _pile_losing_point_dump_override(self, piles, valid, game, player, chosen_pi):
        """Guardrail: as pile follower, don't leak points on a trick that cannot be won."""
        if game.state!=State.PLAY_PILE_FOLLOWER or not game.trick_cards:
            return chosen_pi
        led=game.led_suit
        trump=game.trump_suit
        if led is None or trump is None:
            return chosen_pi
        top_cards={}
        for pi in valid:
            try:
                pile=piles[player][pi]
            except Exception:
                continue
            if pile:
                top_cards[pi]=pile[-1]
        if len(top_cards)<=1:
            return chosen_pi
        chosen=top_cards.get(chosen_pi)
        if chosen is None:
            return chosen_pi
        best_pre=max((c.trick_power(led, trump) for c,_ in game.trick_cards), default=-1)
        if any(c.trick_power(led, trump)>best_pre for c in top_cards.values()):
            return chosen_pi
        if chosen.points()==0:
            return chosen_pi
        safe=[pi for pi,c in top_cards.items() if c.points()==0]
        if not safe:
            return chosen_pi
        return min(
            safe,
            key=lambda pi: (
                top_cards[pi].trick_power(led, trump),
                RANK_ORDER.get(top_cards[pi].rank, 0),
                pi,
            ),
        )

    def _player_has_rank_bridge(self, game, player, suit, low_rank_idx, high_rank_idx):
        """Return True when player owns all same-suit ranks strictly between low/high indices."""
        if suit not in SUITS:
            return False
        lo=int(low_rank_idx)
        hi=int(high_rank_idx)
        if hi-lo<=1:
            return True
        owned=set()
        try:
            for c in game.hands[player]:
                if c.suit==suit:
                    owned.add(c.rank)
            for pile in game.piles[player]:
                for c in pile:
                    if c.suit==suit:
                        owned.add(c.rank)
        except Exception:
            return False
        for ri in range(lo+1, hi):
            if RANKS[ri] not in owned:
                return False
        return True

    def _pile_minimum_sufficient_winner_override(self, piles, valid, game, player, chosen_pi):
        """Guardrail: avoid overkilling pile tricks when a lower guaranteed winner exists."""
        if game.state not in (State.PLAY_PILE_LEADER, State.PLAY_PILE_FOLLOWER):
            return chosen_pi
        if not game.trick_cards:
            return chosen_pi
        led=game.led_suit
        trump=game.trump_suit
        if led is None or trump is None:
            return chosen_pi
        top_cards={}
        for pi in valid:
            try:
                pile=piles[player][pi]
            except Exception:
                continue
            if pile:
                top_cards[pi]=pile[-1]
        if len(top_cards)<=1:
            return chosen_pi
        chosen=top_cards.get(chosen_pi)
        if chosen is None:
            return chosen_pi
        base_seq=list(game.trick_cards)
        def _winner(seq):
            best=-1
            winner=None
            for c,p in seq:
                pw=c.trick_power(led, trump)
                if pw>best:
                    best=pw
                    winner=p
            return winner
        guaranteed=[]
        for pi,card in top_cards.items():
            seq_after=list(base_seq)
            seq_after.append((card, player))
            if _winner(seq_after)!=player:
                continue
            if game.state==State.PLAY_PILE_LEADER:
                opp=1-player
                try:
                    opp_valid=_get_valid_pile(piles, opp, led)
                except Exception:
                    opp_valid=[]
                safe=True
                for oi in opp_valid:
                    try:
                        opp_pile=piles[opp][oi]
                    except Exception:
                        continue
                    if not opp_pile:
                        continue
                    opp_top=opp_pile[-1]
                    if not opp_top.face_up:
                        continue
                    seq_full=list(seq_after)
                    seq_full.append((opp_top, opp))
                    if _winner(seq_full)!=player:
                        safe=False
                        break
                if not safe:
                    continue
            guaranteed.append(pi)
        if len(guaranteed)<=1 or chosen_pi not in guaranteed:
            return chosen_pi
        base=min(
            guaranteed,
            key=lambda pi: (
                top_cards[pi].trick_power(led, trump),
                top_cards[pi].points(),
                RANK_ORDER.get(top_cards[pi].rank, 0),
                pi,
            ),
        )
        if base==chosen_pi:
            return chosen_pi
        low=top_cards[base]
        high=top_cards[chosen_pi]
        if low.suit==high.suit:
            lo_i=RANK_ORDER.get(low.rank, 0)
            hi_i=RANK_ORDER.get(high.rank, 0)
            if hi_i>lo_i and self._player_has_rank_bridge(game, player, high.suit, lo_i, hi_i):
                return chosen_pi
        return base

    def _hand_follow_minimum_sufficient_winner_override(self, hand, valid, game, chosen_idx):
        """Hard guardrail: as hand follower, use the cheapest visible-pile-safe winner under pressure."""
        if game.state!=State.PLAY_HAND_FOLLOWER or len(valid)<=1 or not game.trick_cards:
            return chosen_idx
        led=game.led_suit
        trump=game.trump_suit
        if led is None or trump is None:
            return chosen_idx
        actor=game.active_player()
        if actor not in (0, 1):
            actor=AI_PLAYER
        opp=1-actor
        chosen_card=hand[chosen_idx]
        best_pre=max((c.trick_power(led, trump) for c,_ in game.trick_cards), default=-1)
        winners=[i for i in valid if hand[i].trick_power(led, trump)>best_pre]
        if not winners:
            return chosen_idx
        pot=sum(c.points() for c,_ in game.trick_cards)
        pressure=(game.bid_winner==opp) or (game.trick_num>=6) or (pot>0)
        if not pressure and chosen_idx in winners:
            return chosen_idx

        def _winner(seq):
            best=-1
            w=None
            for c,p in seq:
                pw=c.trick_power(led, trump)
                if pw>best:
                    best=pw
                    w=p
            return w

        def _is_guaranteed(i):
            seq_base=list(game.trick_cards)
            seq_base.append((hand[i], actor))
            if _winner(seq_base)!=actor:
                return False
            try:
                opp_valid=game.get_valid_piles(opp)
            except Exception:
                opp_valid=[]
            if not opp_valid:
                return True
            ai_valid_cache=None
            for opi in opp_valid:
                try:
                    opile=game.piles[opp][opi]
                except Exception:
                    continue
                if not opile:
                    continue
                oc=opile[-1]
                seq_opp=list(seq_base)
                seq_opp.append((oc, opp))
                try:
                    if ai_valid_cache is None:
                        ai_valid_cache=game.get_valid_piles(actor)
                    ai_valid=list(ai_valid_cache or [])
                except Exception:
                    ai_valid=[]
                if not ai_valid:
                    if _winner(seq_opp)!=actor:
                        return False
                    continue
                can_retake=False
                for api in ai_valid:
                    try:
                        apile=game.piles[actor][api]
                    except Exception:
                        continue
                    if not apile:
                        continue
                    ac=apile[-1]
                    seq_full=list(seq_opp)
                    seq_full.append((ac, actor))
                    if _winner(seq_full)==actor:
                        can_retake=True
                        break
                if not can_retake:
                    return False
            return True

        guaranteed=[i for i in winners if _is_guaranteed(i)]
        if guaranteed:
            return min(
                guaranteed,
                key=lambda i: (
                    hand[i].trick_power(led, trump),
                    RANK_ORDER.get(hand[i].rank, 0),
                    hand[i].points(),
                    i,
                ),
            )
        if not pressure:
            return chosen_idx
        return max(
            winners,
            key=lambda i: (
                hand[i].trick_power(led, trump),
                RANK_ORDER.get(hand[i].rank, 0),
                -hand[i].points(),
                -i,
            ),
        )

    def _lead_control_card_guard_override(self, hand, valid, game, chosen_idx):
        """Hard guardrail: on late defensive leads, avoid leaking initiative with low control-suit leads."""
        if game.state!=State.PLAY_HAND_LEADER or len(valid)<=1:
            return chosen_idx
        actor=game.active_player()
        if actor not in (0, 1):
            actor=AI_PLAYER
        opp=1-actor
        if game.bid_winner!=opp or game.trick_num<5:
            return chosen_idx
        chosen=hand[chosen_idx]
        trump=game.trump_suit
        if trump is None or chosen.suit==trump:
            return chosen_idx
        same=[i for i in valid if hand[i].suit==chosen.suit]
        if len(same)<=1:
            return chosen_idx
        higher=[i for i in same if RANK_ORDER.get(hand[i].rank, 0)>RANK_ORDER.get(chosen.rank, 0)]
        if not higher:
            return chosen_idx
        if RANK_ORDER.get(chosen.rank, 0)>=9 and chosen.points()>0:
            return chosen_idx
        controls=[i for i in higher if hand[i].rank in ("A", "K")]
        if not controls:
            return chosen_idx
        return max(controls, key=lambda i: (RANK_ORDER.get(hand[i].rank, 0), hand[i].points(), -i))

    def _pile_leader_hidden_value_exposure_override(self, piles, valid, game, player, chosen_pi):
        """Hard guardrail: avoid peeling low cover cards that reveal strong hidden value when a safe win exists."""
        if game.state!=State.PLAY_PILE_LEADER or len(valid)<=1 or not game.trick_cards:
            return chosen_pi
        led=game.led_suit
        trump=game.trump_suit
        if led is None or trump is None:
            return chosen_pi
        if game.bid_winner!=1-player:
            return chosen_pi
        top_cards={}
        for pi in valid:
            try:
                pile=piles[player][pi]
            except Exception:
                continue
            if pile:
                top_cards[pi]=pile[-1]
        if chosen_pi not in top_cards or len(top_cards)<=1:
            return chosen_pi
        base_seq=list(game.trick_cards)

        def _winner(seq):
            best=-1
            w=None
            for c,p in seq:
                pw=c.trick_power(led, trump)
                if pw>best:
                    best=pw
                    w=p
            return w

        def _guaranteed(pi):
            seq_after=list(base_seq)
            seq_after.append((top_cards[pi], player))
            if _winner(seq_after)!=player:
                return False
            opp=1-player
            try:
                opp_valid=_get_valid_pile(piles, opp, led)
            except Exception:
                opp_valid=[]
            for oi in opp_valid:
                try:
                    opp_pile=piles[opp][oi]
                except Exception:
                    continue
                if not opp_pile:
                    continue
                oc=opp_pile[-1]
                seq_full=list(seq_after)
                seq_full.append((oc, opp))
                if _winner(seq_full)!=player:
                    return False
            return True

        guaranteed=[pi for pi in top_cards if _guaranteed(pi)]
        if chosen_pi not in guaranteed or len(guaranteed)<=1:
            return chosen_pi
        pot=sum(c.points() for c,_ in base_seq)
        if pot>0:
            return chosen_pi

        def _exposure_cost(pi):
            pile=piles[player][pi]
            top=top_cards[pi]
            beneath=pile[-2] if len(pile)>=2 else None
            cost=0.10*RANK_ORDER.get(top.rank, 0)
            if beneath is None:
                cost+=3.0
                return cost
            if beneath.suit==trump:
                cost+=8.0+0.4*RANK_ORDER.get(beneath.rank, 0)
            cost+=beneath.points()*1.5
            if beneath.suit==led:
                cost+=1.0
            return cost

        best=min(
            guaranteed,
            key=lambda pi: (
                _exposure_cost(pi),
                top_cards[pi].trick_power(led, trump),
                top_cards[pi].points(),
                pi,
            ),
        )
        if best==chosen_pi:
            return chosen_pi
        if _exposure_cost(best)+1.5<_exposure_cost(chosen_pi):
            return best
        return chosen_pi

    def _hand_follow_pile_ruff_trap_override(self, hand, valid, game, chosen_idx):
        """Guardrail: when pile phase likely loses to a visible ruff, slough the cheapest follow card."""
        if game.state!=State.PLAY_HAND_FOLLOWER or len(valid)<=1:
            return chosen_idx
        led=game.led_suit
        trump=game.trump_suit
        if led is None or trump is None or led==trump:
            return chosen_idx
        if not any(hand[i].suit==led for i in valid):
            return chosen_idx
        opp=1-AI_PLAYER
        try:
            if game.trick_leader in (0, 1):
                opp=int(game.trick_leader)
        except Exception:
            opp=1-AI_PLAYER

        def _tops_after_reveal(player):
            tops={}
            try:
                plist=game.piles[player]
            except Exception:
                return tops
            for pi,pile in enumerate(plist):
                if pile:
                    tops[pi]=pile[-1]
            return tops

        def _valid_from_tops(tops):
            if not tops:
                return []
            vis=list(tops.keys())
            m=[pi for pi in vis if tops[pi].suit==led]
            return m if m else vis

        opp_tops=_tops_after_reveal(opp)
        opp_valid=_valid_from_tops(opp_tops)
        if not opp_valid:
            return chosen_idx
        opp_forced_led=all(opp_tops[pi].suit==led for pi in opp_valid)
        opp_trumps=[opp_tops[pi] for pi in opp_valid if opp_tops[pi].suit==trump]
        if opp_forced_led or not opp_trumps:
            return chosen_idx

        ai_tops=_tops_after_reveal(AI_PLAYER)
        ai_valid=_valid_from_tops(ai_tops)
        ai_trumps=[ai_tops[pi] for pi in ai_valid if ai_tops[pi].suit==trump]
        if ai_trumps:
            opp_best=max(RANK_ORDER.get(c.rank, 0) for c in opp_trumps)
            ai_best=max(RANK_ORDER.get(c.rank, 0) for c in ai_trumps)
            if ai_best>opp_best:
                return chosen_idx

        return min(
            valid,
            key=lambda i: (
                hand[i].points(),
                RANK_ORDER.get(hand[i].rank, 0),
                i,
            ),
        )

    def _background_ranking_if_fresh(self, game):
        """Return cached background ranking if it matches the exact current state."""
        key=self._state_key(game)
        with self._bg_lock:
            snap=self._bg_result
            if not snap or snap.get("key")!=key:
                return None, None
            ranked=list(snap.get("ranked") or [])
            pv=list(snap.get("pv") or [])
        return ranked, pv

                                                                                                                                                      
    def decide_play_card(self, hand, valid, game, is_leading):
                                                                                                                                                                                                                           
        """Choose hand-card index via MC sampled minimax + heuristic fallbacks."""
        x=self._encode_shared_state(game)
        pri=self.shared_net.infer(x, context=self._belief_context(game))
        if len(valid)==1:
            self._record_match_example(x, "hand", valid[0])
            return valid[0]
        profile=self._runtime_search_profile(mode="fg")
                                                                                                                                                                       
        budget=max(0.06, self._time_budget(game)*float(profile["budget_scale"]))
                                                                                                                                                                       
        deadline=_time.monotonic()+budget
        if game.trick_num>=10:
            depth=6 if budget>1.20 else 5 if budget>0.70 else 4
            sample_scale=40
        elif game.trick_num>=6:
            depth=5 if budget>1.00 else 4 if budget>0.45 else 3
            sample_scale=34
        else:
            depth=4 if budget>0.75 else 3 if budget>0.35 else 2
            sample_scale=28
        depth=max(1, depth+int(profile["depth_delta"]))
        n_samples=min(int(profile["sample_cap"]), min(MC_SAMPLES, max(12, int(budget*sample_scale))))
        ranked,pv=self._background_ranking_if_fresh(game)
        use_bg=bool(ranked) and ranked[0].get("samples", 0)>=12
        if not use_bg:
            self._fg_search_active.set()
            try:
                ranked,pv=self._rank_from_game_state(game, deadline, depth, n_samples, mode="fg")
            finally:
                self._fg_search_active.clear()
        if not ranked:
            bg_ranked,bg_pv=self._background_ranking_if_fresh(game)
            if bg_ranked:
                ranked,pv=bg_ranked,bg_pv
                                                                                                                                                                    
        if ranked:
                                                                                                                                                                
            self.last_analysis=[(r["label"], r.get("display_ev", r["ev"]), r["prob"], r["samples"], r["nodes"]) for r in ranked[:5]]
                                                                                                                                                                              
            self.last_pv=pv[:12] if pv else ["analysis pending"]
            ev_map={r["idx"]: float(r.get("display_ev", r["ev"])) for r in ranked if r["kind"]=="hand"}
            kb_map={r["idx"]: float(r.get("knowledge_bonus", 0.0)) for r in ranked if r["kind"]=="hand"}
            ev_vals=[ev_map.get(i, -9999.0) for i in valid]
            ev_min=min(ev_vals); ev_max=max(ev_vals); ev_den=max(1e-9, ev_max-ev_min)
            kb_vals=[kb_map.get(i, 0.0) for i in valid]
            kb_min=min(kb_vals); kb_max=max(kb_vals); kb_den=max(1e-9, kb_max-kb_min)
            best_idx=valid[0]; best_score=-1e18
            for i in valid:
                ev_n=(ev_map.get(i, ev_min)-ev_min)/ev_den
                kb_n=(kb_map.get(i, kb_min)-kb_min)/kb_den if kb_den>1e-9 else 0.5
                pol=float(pri["hand_logits"][i])
                score=0.64*ev_n+0.22*pol+0.14*kb_n
                if score>best_score:
                    best_score=score; best_idx=i
                                                                                                                                                   
        else:
            best_idx=self._masked_argmax(pri["hand_logits"], valid)
                                                                                                                                                                       
        top_ev=self.last_analysis[0][1] if self.last_analysis else 0.0

        if top_ev<0:
            non_value=[i for i in valid if hand[i].points()==0]
            best_idx=min(non_value, key=lambda i:RANK_ORDER[hand[i].rank]) if non_value else min(valid, key=lambda i:RANK_ORDER[hand[i].rank])
        elif not is_leading and game.trick_cards:
            # Follower: apply trick-win reasoning to avoid dumping points on losing tricks
            try:
                trump = game.trump_suit; led = game.led_suit
                if led and trump:
                    best_pre = max(c.trick_power(led, trump) for c, _ in game.trick_cards)
                    can_win = any(hand[i].trick_power(led, trump) > best_pre for i in valid)
                    if not can_win:
                        # Cannot win this trick — prefer lowest point card
                        best_idx = min(valid, key=lambda i: (hand[i].points(), RANK_ORDER[hand[i].rank]))
            except Exception:
                pass
                                                                                                                                                                                                                                    
        if random.random()<self.epsilon:
            best_idx=random.choice(valid)
        # Opening lead override: trick 1 leader uses RoundPlan convention
        if is_leading and game.trick_num==1:
            ol=self._pick_opening_lead(hand, valid, game)
            if ol is not None:
                best_idx=ol
        best_idx=self._critical_void_trump_override(hand, valid, game, best_idx)
        best_idx=self._lead_pile_ruff_trap_override(hand, valid, game, best_idx)
        best_idx=self._hand_follow_pile_ruff_trap_override(hand, valid, game, best_idx)
        best_idx=self._hand_follow_minimum_sufficient_winner_override(hand, valid, game, best_idx)
        best_idx=self._lead_control_card_guard_override(hand, valid, game, best_idx)
        # Apply reason_trick_win safety override:
        # When leading with initiative, avoid suits the tracker marks as dangerous
        if is_leading and len(valid) > 1 and game.trump_suit:
            try:
                trick_reasons = self.reason_trick_win(hand, valid, game)
                chosen = trick_reasons.get(best_idx, {})
                if not chosen.get('safe', True) and chosen.get('wins', True):
                    # Current pick is unsafe lead — try to find a safer alternative
                    safe_alts = [i for i in valid if i != best_idx
                                 and trick_reasons.get(i, {}).get('safe', True)]
                    if safe_alts:
                        # Prefer safe alt with highest EV (if ranked) or lowest risk
                        if ranked:
                            ev_map_local = {r["idx"]: r.get("display_ev", r["ev"]) for r in ranked if r["kind"] == "hand"}
                            safe_alts.sort(key=lambda i: ev_map_local.get(i, -9999.0), reverse=True)
                        alt = safe_alts[0]
                        # Only override if alt has no point loss and small EV difference
                        alt_ev = ev_map.get(alt, -9999.0) if ranked else 0.0
                        best_ev = ev_map.get(best_idx, -9999.0) if ranked else 0.0
                        if alt_ev >= best_ev - 8.0:
                            best_idx = alt
            except Exception:
                pass
        self._record_match_example(x, "hand", best_idx)
        return best_idx

                                                                                                                                                      
    def decide_pile_card(self, piles, valid, game, player):
                                                                                                                                                                          
        """Choose pile index from visible tops using heuristic + NN blend."""
        x=self._encode_shared_state(game)
        pri=self.shared_net.infer(x, context=self._belief_context(game))
        if len(valid)==1:
            self._record_match_example(x, "pile", valid[0])
            return valid[0]
        profile=self._runtime_search_profile(mode="fg")
        deadline=_time.monotonic()+max(0.08, self._time_budget(game)*0.42*float(profile["budget_scale"]))
        depth=max(2, min(4, BG_TREE_DEPTH-1 if game.trick_num>=7 else BG_TREE_DEPTH-2)+int(profile["depth_delta"]))
        samples=max(10, min(int(profile["sample_cap"]), min(MC_SAMPLES//2, int(max(0.10, deadline-_time.monotonic())*36))))
        ranked,pv=self._background_ranking_if_fresh(game)
        use_bg=bool(ranked) and ranked[0].get("samples", 0)>=8
        if not use_bg:
            self._fg_search_active.set()
            try:
                ranked,pv=self._rank_from_game_state(game, deadline, depth, samples, mode="fg")
            finally:
                self._fg_search_active.clear()
        if not ranked:
            bg_ranked,bg_pv=self._background_ranking_if_fresh(game)
            if bg_ranked:
                ranked,pv=bg_ranked,bg_pv
                                                                                                                                                                    
        if ranked:
                                                                                                                                                                
            self.last_analysis=[(r["label"], r.get("display_ev", r["ev"]), r["prob"], r["samples"], r["nodes"]) for r in ranked[:5]]
                                                                                                                                                                              
            self.last_pv=pv[:12] if pv else self.last_pv
            ev_map={r["idx"]: float(r.get("display_ev", r["ev"])) for r in ranked if r["kind"]=="pile"}
            kb_map={r["idx"]: float(r.get("knowledge_bonus", 0.0)) for r in ranked if r["kind"]=="pile"}
            ev_vals=[ev_map.get(i, -9999.0) for i in valid]
            ev_min=min(ev_vals); ev_max=max(ev_vals); ev_den=max(1e-9, ev_max-ev_min)
            kb_vals=[kb_map.get(i, 0.0) for i in valid]
            kb_min=min(kb_vals); kb_max=max(kb_vals); kb_den=max(1e-9, kb_max-kb_min)
            best_pi=valid[0]; best_score=-1e18
            for pi in valid:
                ev_n=(ev_map.get(pi, ev_min)-ev_min)/ev_den
                kb_n=(kb_map.get(pi, kb_min)-kb_min)/kb_den if kb_den>1e-9 else 0.5
                pol=float(pri["pile_logits"][pi])
                score=0.64*ev_n+0.22*pol+0.14*kb_n
                if score>best_score:
                    best_score=score; best_pi=pi
                                                                                                                                                   
        else:
            best_pi=self._masked_argmax(pri["pile_logits"], valid)
                                                                                                                                                                                                                                    
        if random.random()<self.epsilon:
                                                                                                                                                                             
            best_pi=random.choice(valid)
        best_pi=self._pile_losing_point_dump_override(piles, valid, game, player, best_pi)
        best_pi=self._pile_minimum_sufficient_winner_override(piles, valid, game, player, best_pi)
        best_pi=self._pile_leader_hidden_value_exposure_override(piles, valid, game, player, best_pi)
        self._record_match_example(x, "pile", best_pi)

        return best_pi

    def reason_trick_win(self, hand, valid, game):
        """Analyze each valid card and return reasoning about trick-winning potential.

        Returns dict: {card_idx: {'wins': bool, 'safe': bool, 'pts_at_stake': int, 'reason': str}}

        When leading (initiative): assesses control retention vs ruff/overcard risk.
        When following: assesses win/dump decision with minimum-winner logic.
        Uses CardTracker's void model and opponent probability estimates.
        """
        trump = game.trump_suit
        led = game.led_suit
        is_leading = (game.state == State.PLAY_HAND_LEADER)
        try:
            opp_model = self._opponent_play_model(game, AI_PLAYER)
        except Exception:
            opp_model = {}

        result = {}
        for i in valid:
            if i < 0 or i >= len(hand):
                continue
            card = hand[i]
            info = {}
            try:
                if is_leading:
                    lead_suit = card.suit
                    p_follow = self._opponent_can_hold(opp_model, lambda oc, ls=lead_suit: oc.suit == ls)
                    p_higher = self._opponent_can_hold(
                        opp_model,
                        lambda oc, ls=lead_suit, cr=card.rank: oc.suit == ls and RANK_ORDER[oc.rank] > RANK_ORDER[cr],
                    )
                    p_trump_ruff = 0.0
                    if trump and lead_suit != trump:
                        p_has_trump = self._opponent_can_hold(opp_model, lambda oc, ts=trump: oc.suit == ts)
                        p_void_led = max(0.0, 1.0 - p_follow)
                        p_trump_ruff = p_void_led * p_has_trump
                    p_lose = min(1.0, p_higher + p_trump_ruff)

                    info['wins'] = True
                    info['safe'] = p_lose < 0.30
                    info['pts_at_stake'] = card.points()
                    known_void = lead_suit in self.tracker.void_suits[HUMAN]
                    tc = sum(1 for c in hand if c.suit == trump) if trump else 0
                    if card.rank == 'A':
                        info['reason'] = f"Ace {lead_suit} — unbeatable in suit; P(ruff)={p_trump_ruff:.0%}"
                    elif card.rank == 'K':
                        info['reason'] = f"King {lead_suit} — P(opp has Ace)={p_higher:.0%} P(ruff)={p_trump_ruff:.0%}"
                    elif card.suit == trump:
                        info['reason'] = f"Trump lead {card.rank}{trump} — {tc} trumps held; draws opp trumps"
                    elif known_void:
                        info['reason'] = f"DANGER: {lead_suit} lead but opp KNOWN VOID — ruff imminent!"
                        info['safe'] = False
                    else:
                        safe_conf = self.tracker.safe_to_lead_suit(lead_suit, trump, hand)
                        info['reason'] = (
                            f"Lead {card.rank}{lead_suit} — P(lose)={p_lose:.0%} "
                            f"safety={safe_conf:.0%}"
                        )
                else:
                    # Following
                    if not game.trick_cards:
                        info['wins'] = False; info['safe'] = True
                        info['pts_at_stake'] = 0
                        info['reason'] = "No trick in progress"
                    else:
                        best_pre = max(c.trick_power(led, trump) for c, _ in game.trick_cards)
                        my_power = card.trick_power(led, trump)
                        pot = sum(c.points() for c, _ in game.trick_cards)
                        info['wins'] = my_power > best_pre
                        info['pts_at_stake'] = pot + card.points()
                        void_in_led = bool(led) and not any(hand[j].suit == led for j in valid if j < len(hand))
                        if void_in_led and card.suit == trump and info['wins']:
                            info['safe'] = True
                            info['reason'] = f"RUFF {card.rank}{trump} — void in {led}; takes pot={pot}pts"
                        elif void_in_led and card.suit != trump:
                            info['safe'] = (pot == 0 and card.points() == 0)
                            info['reason'] = f"Slough {card.rank}{card.suit} — no trump; pot={pot}pts"
                        elif info['wins']:
                            winners = [hand[j] for j in valid if j < len(hand)
                                       and hand[j].trick_power(led, trump) > best_pre]
                            is_min = (len(winners) > 1 and
                                      RANK_ORDER[card.rank] == min(RANK_ORDER[c.rank] for c in winners))
                            info['safe'] = True
                            tag = "min-winner" if is_min else "winner"
                            info['reason'] = f"{tag.title()} {card.rank}{card.suit} — takes pot={pot}pts"
                        else:
                            info['safe'] = (card.points() == 0)
                            if card.points() > 0:
                                info['reason'] = f"DUMP {card.rank}{card.suit} ({card.points()}pts) — LOSING trick! pot={pot}pts"
                            else:
                                info['reason'] = f"Safe duck {card.rank}{card.suit} — 0pts, pot={pot}pts"
            except Exception as ex:
                info.setdefault('wins', False); info.setdefault('safe', True)
                info.setdefault('pts_at_stake', 0); info.setdefault('reason', f"err: {ex}")
            result[i] = info
        return result

    def should_lead_suit_now(self, hand, suit, game):
        """Return True when it is strategically optimal to lead this suit as initiative card.

        Conditions favouring a lead:
        - We hold the top card (Ace, or King if Ace gone)
        - Opponent is NOT known void (safe from ruff)
        - Suit has hidden point cards (10, A, 5) we want to flush out
        - Opponent is short/void in OTHER suits that we control
        """
        trump = game.trump_suit
        led = game.led_suit
        if led is not None:
            return False  # Not leading yet
        tracker = self.tracker
        # Void check: if opp is void, leading this suit (non-trump) lets them ruff
        if suit != trump and suit in tracker.void_suits[HUMAN]:
            return False
        # Check we hold top card in this suit
        our_cards = [c for c in hand if c.suit == suit]
        if not our_cards:
            return False
        top_rank = max(our_cards, key=lambda c: RANK_ORDER[c.rank])
        si = SUITS.index(suit)
        higher_out = any(
            si * 13 + ri not in tracker.played and si * 13 + ri not in tracker.my_hand
            for ri in range(RANK_ORDER[top_rank.rank] + 1, 13)
        )
        if higher_out:
            return False  # Opponent may hold a higher card
        # Check suit has value cards (worth flushing)
        val_cards_remaining = sum(
            1 for ri, rk in enumerate(RANKS)
            if rk in ('5', '10', 'A') and (si * 13 + ri) not in tracker.played
        )
        return val_cards_remaining > 0



    def decide_bid(self,hand):
                                                                                                                                                                          
        """Choose opening bid from heuristic hand estimate + bid network output."""
        game=self._current_game
        if game is None:
            game=type("G", (), {})()
            game.piles=[[],[]]; game.trick_cards=[]; game.trick_num=0; game.bid_amount=0
            game.bid_winner=None; game.trick_leader=AI_PLAYER; game.active_player=lambda : AI_PLAYER
            game.tricks_won=[0,0]; game.cards_won=[[],[]]; game.scores=[0,0]; game.round_num=0
            game.current_bid=MIN_BID; game.clock=type("C", (), {"rem":[1.0,1.0], "initial":[1.0,1.0]})()
            game.match_target=1000; game.trump_suit=None; game.state=State.BIDDING
        x=self._encode_shared_state(game)
        p=self.shared_net.infer(x, context=self._belief_context(game))
        bid_idx=self._masked_argmax(p["bid_logits"], list(range(len(self.BID_ACTIONS))))
        bid_from_head=self._bid_amount_from_idx(bid_idx)
        heuristic=self._opening_bid_heuristic(hand)
        cap=self._bid_contract_cap(hand, p["value"])
        bid=self._round_bid(0.6*bid_from_head+0.4*heuristic)
        bid=max(MIN_BID, min(MAX_BID, min(cap, bid)))
        if cap<=MIN_BID and heuristic<=BID_WEAK_OPEN_PASS and float(p["value"])<0.20:
            bid=0
        if random.random()<self.epsilon:
            explore=[0]+[b for b in self.BID_ACTIONS if b<=cap]
            bid=random.choice(explore) if explore else 0
        self.round_bid_feat=x.copy(); self.round_bid_amount=bid
        if bid>=MIN_BID:
            self._record_match_example(x, "bid", self._bid_idx_from_amount(bid))
        return bid

                                                                                                                                                      
    def decide_should_bid(self,hand,cur):
                                                                                                                                                                          
        """Decide whether to raise current bid by one legal increment."""
        game=self._current_game
        if game is None:
            return False
        x=self._encode_shared_state(game)
        p=self.shared_net.infer(x, context=self._belief_context(game))
        valid=[i for i,b in enumerate(self.BID_ACTIONS) if b>=cur+5]
        if not valid:
            return False
        best_idx=self._masked_argmax(p["bid_logits"], valid)
        best_bid=self._bid_amount_from_idx(best_idx)
        cap=self._bid_contract_cap(hand, p["value"])
        target=cur+5
        should=target<=cap and best_bid>=target
        score_gap=int(game.scores[HUMAN])-int(game.scores[AI_PLAYER])
        # Desperation only when strictly within cap and NN confirms the hand
        if score_gap>=300 and target<=cap and best_bid>=target:
            should=True
        if random.random()<self.epsilon:
            should=(target<=cap) and (random.random()<0.25)
        self.round_bid_feat=x.copy(); self.round_bid_amount=cur+5
        if should:
            self._record_match_example(x, "bid", best_idx)
        return should

                                                                                                                                                      
    def decide_discard(self,hand):
                                                                                                                                                                          
        """Pick four discard indices after taking special cards."""
                                                                                                                                                                       
        trump,_,_=self._eval_hand(hand); scores=[]
                                                                                                                                                                      
        for i,c in enumerate(hand):
                                                                                                                                                                           
            s=0
                                                                                                                                                                        
            if c.suit==trump: s+=50+RANK_ORDER[c.rank]*2
                                                                                                                                                       
            else: s+=RANK_ORDER[c.rank]*3+(30 if c.rank=="A" else 20 if c.rank=="K" else 0)
                                                                                                                                                                        
            if c.points()>0: s+=c.points()*2
                                                                                                                                                                
            scores.append((s,i))
                                                                                                                                                            
        scores.sort(); return set(idx for _,idx in scores[:4])

                                                                                                                                                      
    def decide_trump(self,hand):
                                                                                                                                                                          
        """Pick trump suit from hand heuristic evaluation."""
                                                                                                                                                  
        return self._eval_hand(hand)[0]

                                                               
                                                                                                                                                                                                                      
    def learn_from_round(self,ai_delta,opp_delta,bid_amount,was_bidder,ai_raw):
                                                                                                                                                                          
        """Round-level bookkeeping; shared network updates are applied on match-end targets."""
        self.epsilon=max(0.01, self.epsilon*0.998)
        self.games_played+=1
        self.round_bid_feat=None
    def learn_from_match(self, ai_score, opp_score, winner):
        """Train all heads with self-play trajectories and final match outcome target."""
        if not self.match_examples:
            return
        scale=max(1.0, float(abs(ai_score)+abs(opp_score)))
        value_target=float(np.clip((ai_score-opp_score)/scale, -1.0, 1.0))
        if winner==AI_PLAYER:
            value_target=max(value_target, 0.2)
        elif winner==HUMAN:
            value_target=min(value_target, -0.2)
        batch=list(self.match_examples)
        if len(batch)>2048:
            batch=random.sample(batch, 2048)
        for x,head,aidx in batch:
            self.shared_net.train_step(x, policy_head=head, action_idx=aidx, value_target=value_target,
                                       policy_weight=1.0, value_weight=0.45)
        self.match_examples.clear()
        self.epsilon=max(0.008, self.epsilon*0.995)
        if self.games_played%2==0:
            self.save()

                                                                   

                                                                                                                                                  
class ShelemGame:
                                                                                                                                                                      
    """Core game state machine and rules engine independent of rendering."""
                                                                                                                                                      
    def __init__(self,match_target=1000):
                                                                                                                                                                          
        self.match_target=match_target
                                                                                                                                                                          
        self.scores=[0,0]; self.round_num=0; self.first_dealer=0
                                                                                                                                                            
        self.state=State.MATCH_START; self.clock=ChessClock(600,600)
                                                                                                                                                                          
        self.message=""; self.sub_message=""; self.match_winner=None
                                                                                                                                                                          
        self.auto_timer=0; self.shelem_player=None; self.shelem_start=0

                                                                                                                                                      
    def new_round(self):
                                                                                                                                                                          
        """Deal a fresh round, reset transient state, and enter bidding."""
                                                                                                                                                            
        self.round_num+=1; deck=make_deck()
                                                                                                                                                                          
        self.hands=[deck[:12],deck[12:24]]
                                                                                                                                                            
        sort_hand(self.hands[0]); sort_hand(self.hands[1])
                                                                                                                                                                          
        self.special_pile=deck[24:28]
                                                                                                                                                                       
        idx=28; self.piles=[[],[]]
                                                                                                                                                                      
        for p in range(2):
                                                                                                                                                                          
            for _ in range(4):
                                                                                                                                                                               
                pile=deck[idx:idx+3]
                                                                                                                                                                              
                for c in pile: c.face_up=False
                                                                                                                                                                    
                self.piles[p].append(pile); idx+=3
                                                                                                                                                                          
        self.trump_suit=None; self.bid_winner=None; self.bid_amount=0
                                                                                                                                                                          
        self.current_bid=MIN_BID; self.bidder_turn=self.first_dealer
                                                                                                                                                                          
        self.bid_passed=[False,False]; self.last_bid=[0,0]
                                                                                                                                                                          
        self.trick_leader=None; self.tricks_won=[0,0]
                                                                                                                                                                          
        self.cards_won=[[],[]]; self.trick_cards=[]; self.trick_num=0
                                                                                                                                                            
        self.led_suit=None; self.discard_selected=set()
                                                                                                                                                                          
        self.trick_pile_count=[0,0]; self.score_deltas=[0,0]
                                                                                                                                                                          
        self.round_points=[0,0]; self.bonus_msg=""
                                                                                                                                                                          
        self.state=State.BIDDING
                                                                                                                                                            
        self.message=f"Bidding \u2014 {player_name(self.bidder_turn)} first"
                                                                                                                                                                          
        self.sub_message=""; self.first_dealer=1-self.first_dealer
                                                                                                                                                            
        self.clock.reset_round(); self.shelem_player=None

                                                                                                                                                      
    def active_player(self):
                                                                                                                                                                          
        """Return whose turn it is for the current FSM state."""
                                                                                                                                                                       
        s=self.state
                                                                                                                                                                    
        if s==State.BIDDING: return self.bidder_turn
                                                                                                                                                                    
        if s in(State.TAKE_SPECIAL,State.DISCARDING,State.TRUMP_SELECT): return self.bid_winner
                                                                                                                                                                    
        if s==State.PLAY_HAND_LEADER: return self.trick_leader
                                                                                                                                                                    
        if s==State.PLAY_HAND_FOLLOWER: return 1-self.trick_leader
                                                                                                                                                                    
        if s==State.PLAY_PILE_LEADER: return self.trick_leader
                                                                                                                                                                    
        if s==State.PLAY_PILE_FOLLOWER: return 1-self.trick_leader
                                                                                                                                                  
        return None

                                                                                                                                                      
    def place_bid(self,amount):
                                                                                                                                                                          
        """Apply a bid action and advance bidding flow."""
                                                                                                                                                                       
        p=self.bidder_turn; self.last_bid[p]=amount; self.current_bid=amount
                                                                                                                                                                          
        self.bid_passed[p]=False
                                                                                                                                                            
        self.message=f"{player_name(p)} bids ${amount}"
                                                                                                                                                            
        self.bidder_turn=1-p; self._sw(); self._chk_bid()
                                                                                                                                                      
    def pass_bid(self):
                                                                                                                                                                          
        """Apply pass action; redeal if both players pass without opening."""
                                                                                                                                                                       
        p=self.bidder_turn; self.bid_passed[p]=True
                                                                                                                                                                    
        if self.bid_passed[1-p] and self.last_bid[0]==0 and self.last_bid[1]==0:
                                                                                                                                                                
            self.message="Both passed \u2014 re-dealing\u2026"; self.new_round(); return
                                                                                                                                                            
        self.message=f"{player_name(p)} passes"
                                                                                                                                                            
        self.bidder_turn=1-p; self._sw(); self._chk_bid()
                                                                                                                                                      
    def _chk_bid(self):
                                                                                                                                                                          
        """Check whether auction has ended and transition to take-special phase."""
                                                                                                                                                                    
        if self.current_bid>=MAX_BID and not self.bid_passed[self.bidder_turn]:
                                                                                                                                                                              
            self.bid_passed[self.bidder_turn]=True
                                                                                                                                                                    
        if self.bid_passed[0] and not self.bid_passed[1]: self.bid_winner=1
                                                                                                                                                      
        elif self.bid_passed[1] and not self.bid_passed[0]: self.bid_winner=0
                                                                                                                                                      
        elif self.bid_passed[0] and self.bid_passed[1]:
                                                                                                                                                                              
            self.bid_winner=0 if self.last_bid[0]>=self.last_bid[1] else 1
                                                                                                                                                   
        else: return
                                                                                                                                                                          
        self.bid_amount=self.current_bid
                                                                                                                                                            
        self.message=f"{player_name(self.bid_winner)} wins bid at ${self.bid_amount}!"
                                                                                                                                                                          
        self.sub_message=""; self.state=State.TAKE_SPECIAL
                                                                                                                                                            
        self.auto_timer=pygame.time.get_ticks()+800

                                                                                                                                                      
    def take_special(self):
                                                                                                                                                                          
        """Move special cards to bidder hand and start discard step."""
                                                                                                                                                                       
        w=self.bid_winner
                                                                                                                                                                      
        for c in self.special_pile: c.face_up=True
                                                                                                                                                            
        self.hands[w].extend(self.special_pile); sort_hand(self.hands[w])
                                                                                                                                                                          
        self.special_pile=[]; self.state=State.DISCARDING
                                                                                                                                                            
        self.message=f"{player_name(w)}: select 4 to discard"
                                                                                                                                                            
        self.sub_message=""; self.discard_selected=set(); self.clock.start(w)
                                                                                                                                                      
    def toggle_discard(self,idx):
                                                                                                                                                            
        """Toggle selected discard index (up to 4 cards)."""
                                                                                                                                                                    
        if idx in self.discard_selected: self.discard_selected.remove(idx)
                                                                                                                                                      
        elif len(self.discard_selected)<4: self.discard_selected.add(idx)
                                                                                                                                                                       
        n=len(self.discard_selected)
                                                                                                                                                            
        self.sub_message=f"{n}/4 selected"+(" \u2014 Tap Confirm" if n==4 else "")
                                                                                                                                                      
    def confirm_discard(self):
                                                                                                                                                                          
        """Commit selected discards and transition to trump selection."""
                                                                                                                                                                    
        if len(self.discard_selected)!=4: return
                                                                                                                                                                       
        w=self.bid_winner; hand=self.hands[w]
                                                                                                                                                                       
        disc=[hand[i] for i in sorted(self.discard_selected,reverse=True)]
                                                                                                                                                                      
        for i in sorted(self.discard_selected,reverse=True): hand.pop(i)
                                                                                                                                                                          
        self.tricks_won[w]+=1; self.trick_pile_count[w]+=1
                                                                                                                                                            
        self.cards_won[w].extend(disc); self.trick_num=0
                                                                                                                                                            
        sort_hand(self.hands[w]); self.state=State.TRUMP_SELECT
                                                                                                                                                            
        self.message=f"{player_name(w)}: choose trump"
                                                                                                                                                            
        self.sub_message=""; self.discard_selected=set()
                                                                                                                                                  
        return disc                      
                                                                                                                                                      
    def select_trump(self,suit):
                                                                                                                                                                          
        """Set trump suit and start first trick."""
                                                                                                                                                                          
        self.trump_suit=suit; self.trick_leader=self.bid_winner
                                                                                                                                                                          
        self.message=f"Trump: {SUIT_NAMES[suit]} {suit}"
                                                                                                                                                            
        self.sub_message=""; self._start_trick()
                                                                                                                                                      
    def _start_trick(self):
                                                                                                                                                                          
        """Initialize next trick and assign leader turn."""
                                                                                                                                                                          
        self.trick_num+=1; self.trick_cards=[]; self.led_suit=None
                                                                                                                                                                          
        self.state=State.PLAY_HAND_LEADER
                                                                                                                                                            
        self.sub_message=f"Trick {self.trick_num}/12 \u2014 {player_name(self.trick_leader)} leads"
                                                                                                                                                            
        self.clock.switch_to(self.trick_leader)
                                                                                                                                                      
    def get_valid_hand(self,p):
                                                                                                                                                                          
        """Legal hand-card indices for player `p` under follow-suit rule."""
                                                                                                                                                                       
        h=self.hands[p]
                                                                                                                                                                    
        if not self.led_suit: return list(range(len(h)))
                                                                                                                                                                       
        m=[i for i,c in enumerate(h) if c.suit==self.led_suit]
                                                                                                                                                  
        return m if m else list(range(len(h)))
                                                                                                                                                      
    def get_valid_piles(self,p):
                                                                                                                                                                          
        """Legal pile indices for player `p` among visible pile tops."""
                                                                                                                                                                       
        vis=[pi for pi,pile in enumerate(self.piles[p]) if pile and pile[-1].face_up]
                                                                                                                                                                    
        if not vis: return []
                                                                                                                                                                    
        if self.led_suit:
                                                                                                                                                                           
            m=[pi for pi in vis if self.piles[p][pi][-1].suit==self.led_suit]
                                                                                                                                                                        
            if m: return m
                                                                                                                                                  
        return vis
                                                                                                                                                      
    def play_hand(self,player,ci):
                                                                                                                                                                          
        """Play selected hand card and advance to next sub-phase."""
                                                                                                                                                                       
        card=self.hands[player].pop(ci)
                                                                                                                                                                    
        if not self.led_suit: self.led_suit=card.suit
                                                                                                                                                            
        self.trick_cards.append((card,player))
                                                                                                                                                                    
        if self.state==State.PLAY_HAND_LEADER:
                                                                                                                                                                           
            f=1-self.trick_leader; self.state=State.PLAY_HAND_FOLLOWER
                                                                                                                                                                
            self.sub_message=f"Trick {self.trick_num}/12 \u2014 {player_name(f)} follows"
                                                                                                                                                                
            self.clock.switch_to(f)
                                                                                                                                                   
        else:
                                                                                                                                                                          
            for p in range(2):
                                                                                                                                                                              
                for pile in self.piles[p]:
                                                                                                                                                                                
                    if pile and not pile[-1].face_up: pile[-1].face_up=True
                                                                                                                                                                
            self._pile_phase()
                                                                                                                                                  
        return card
                                                                                                                                                      
    def _pile_phase(self):
                                                                                                                                                                          
        """Enter pile sub-phase or resolve immediately if no pile cards remain."""
                                                                                                                                                                       
        l=self.trick_leader; f=1-l
                                                                                                                                                                       
        lh=any(self.piles[l]); fh=any(self.piles[f])
                                                                                                                                                                    
        if lh: self.state=State.PLAY_PILE_LEADER; self.sub_message=f"Trick {self.trick_num}/12 \u2014 {player_name(l)} picks pile"; self.clock.switch_to(l)
                                                                                                                                                      
        elif fh: self.state=State.PLAY_PILE_FOLLOWER; self.sub_message=f"Trick {self.trick_num}/12 \u2014 {player_name(f)} picks pile"; self.clock.switch_to(f)
                                                                                                                                                   
        else: self._resolve()
                                                                                                                                                      
    def play_pile(self,player,pi):
                                                                                                                                                                          
        """Play selected pile-top card and advance/resolve trick."""
                                                                                                                                                                       
        pile=self.piles[player][pi]; card=pile.pop()
                                                                                                                                                            
        self.trick_cards.append((card,player))
                                                                                                                                                                    
        if pile and not pile[-1].face_up: pile[-1].face_up=True
                                                                                                                                                                       
        l=self.trick_leader; f=1-l
                                                                                                                                                                    
        if self.state==State.PLAY_PILE_LEADER:
                                                                                                                                                                        
            if any(self.piles[f]): self.state=State.PLAY_PILE_FOLLOWER; self.sub_message=f"Trick {self.trick_num}/12 \u2014 {player_name(f)} picks pile"; self.clock.switch_to(f)
                                                                                                                                                       
            else: self._resolve()
                                                                                                                                                   
        else: self._resolve()
                                                                                                                                                  
        return card
                                                                                                                                                      
    def _resolve(self):
                                                                                                                                                                          
        """Resolve trick winner, assign captured cards, and enter result state."""
                                                                                                                                                                       
        best=-1; winner=0; wc=None
                                                                                                                                                                      
        for card,pl in self.trick_cards:
                                                                                                                                                                           
            pw=card.trick_power(self.led_suit,self.trump_suit)
                                                                                                                                                                        
            if pw>best: best,winner,wc=pw,pl,card
                                                                                                                                                                          
        self.tricks_won[winner]+=1; self.trick_pile_count[winner]+=1
                                                                                                                                                                      
        for card,_ in self.trick_cards: self.cards_won[winner].append(card)
                                                                                                                                                            
        self.message=f"{player_name(winner)} wins trick {self.trick_num} with {wc}"
                                                                                                                                                            
        self.trick_leader=winner; self.state=State.TRICK_RESULT; self.clock.pause()
                                                                                                                                                            
        self.auto_timer=pygame.time.get_ticks()+AUTO_TRICK_MS
                                                                                                                                                      
    def next_after_trick(self):
                                                                                                                                                                          
        """Advance from trick result to next trick or round-end scoring."""
                                                                                                                                                                          
        self.trick_cards=[]
                                                                                                                                                                    
        if self.trick_num>=12: self._end_round()
                                                                                                                                                   
        else: self._start_trick()

                                                                                                                                                      
    def _end_round(self):
                                                                                                                                                                          
        """Compute final round deltas with Shelem and contract rules."""
                                                                                                                                                                       
        pts=[self.tricks_won[p]*5+card_points(self.cards_won[p]) for p in range(2)]
                                                                                                                                                                          
        self.round_points=pts; w=self.bid_winner; l=1-w
                                                                                                                                                                          
        self.score_deltas=[0,0]
                                                                                                                                                                       
        all_tricks = pts[w]>=TOTAL_PTS                      

                                                                                                                                                                    
        if self.bid_amount>=MAX_BID and all_tricks:
                                                    
                                                                                                                                                                              
            self.score_deltas[w]=330; self.scores[w]+=330
                                                                                                                                                                              
            self.score_deltas[l]=0
                                                                                                                                                                
            self.bonus_msg=f"\U0001f3c6 BIG SHELEM! {player_name(w)} wins $330!"
                                                                                                                                                                
            self.shelem_player=w; self.shelem_start=pygame.time.get_ticks()
                                                                                                                                                                              
            self.state=State.SHELEM_CELEBRATION
                                                                                                                                                      
        elif all_tricks and self.bid_amount<MAX_BID:
                                                                    
                                                                                                                                                                              
            self.score_deltas[w]=215; self.scores[w]+=215
                                                                                                                                                                              
            self.score_deltas[l]=0
                                                                                                                                                                
            self.bonus_msg=f"\u2b50 Small Shelem! {player_name(w)} wins $215!"
                                                                                                                                                                
            self.shelem_player=w; self.shelem_start=pygame.time.get_ticks()
                                                                                                                                                                              
            self.state=State.SHELEM_CELEBRATION
                                                                                                                                                      
        elif pts[w]>=self.bid_amount:
                              
                                                                                                                                                                              
            self.score_deltas[w]=pts[w]; self.scores[w]+=pts[w]
                                                                                                                                                                              
            self.score_deltas[l]=pts[l]; self.scores[l]+=pts[l]
                                                                                                                                                                              
            self.bonus_msg=""; self.state=State.ROUND_END
                                                                                                                                                   
        else:
                                                                            
                                                                                                                                                                           
            penalty=self.bid_amount
                                                                                                                                                                              
            self.score_deltas[w]=-penalty; self.scores[w]-=penalty
                                                                                                                                                                              
            self.score_deltas[l]=pts[l]; self.scores[l]+=pts[l]
                                                                                                                                                                
            self.bonus_msg=(f"{player_name(w)} bid ${self.bid_amount} got ${pts[w]} "
                                                                                                                                                                                              
                            f"\u2014 penalty \u2212${penalty}!")
                                                                                                                                                                              
            self.state=State.ROUND_END

                                                                                                                                                                    
        if self.state==State.ROUND_END:
                                                                                                                                                                              
            self.message=f"Round {self.round_num} Complete"; self.sub_message=""
                                                                                                                                                                
            self.clock.pause()
            self._update_match_winner()
                                                                                                                                                                
            self.auto_timer=pygame.time.get_ticks()+AUTO_ROUND_MS

    def _update_match_winner(self):
        """Resolve winner by either target score or target lead difference."""
        if self.match_winner is not None:
            return
        a=int(self.scores[HUMAN]); b=int(self.scores[AI_PLAYER]); tgt=max(1,int(self.match_target))
        lead=HUMAN if a>b else AI_PLAYER if b>a else None
                                                                 
        if lead is not None and abs(a-b)>=tgt:
            self.match_winner=lead
            return
                                                       
        if (a>=tgt or b>=tgt) and lead is not None:
            self.match_winner=lead

                                                                                                                                                      
    def _sw(self):
                                                                                                                                                                          
        """Sync clock active side with current active player."""
                                                                                                                                                                       
        ap=self.active_player()
                                                                                                                                                                    
        if ap is not None: self.clock.switch_to(ap)
                                                                                                                                                      
    def check_timeout(self):
                                                                                                                                                                          
        """Handle timeout losses and transition to round-end state if needed."""
                                                                                                                                                                    
        if self.state in(State.MATCH_START,State.ROUND_END,State.MATCH_OVER,State.SHELEM_CELEBRATION):
                                                                                                                                                      
            return False
                                                                                                                                                                      
        for p in range(2):
                                                                                                                                                                        
            if self.clock.flagged[p]:
                                                                                                                                                                    
                self.clock.pause(); opp=1-p
                                                                                                                                                                               
                opp_pts=self.tricks_won[opp]*5+card_points(self.cards_won[opp])
                                                                                                                                                                               
                bid_val=max(MIN_BID,self.bid_amount or MIN_BID)
                                                                                                                                                                               
                opp_earn=bid_val+opp_pts
                                                                                                                                                                                  
                self.scores[opp]+=opp_earn
                                                                                                                                                                                  
                self.round_points=[0,0]; self.round_points[opp]=opp_earn
                                                                                                                                                                                  
                self.score_deltas=[0,0]; self.score_deltas[opp]=opp_earn
                                                                                                                                                                                  
                self.bonus_msg=f"{'A' if p==0 else 'B'} timed out! {'A' if opp==0 else 'B'} gets ${opp_earn}"
                                                                                                                                                                                  
                self.trick_cards=[]; self.state=State.ROUND_END
                                                                                                                                                                                  
                self.message=f"Round {self.round_num} \u2014 Time Out!"; self.sub_message=""
                self._update_match_winner()
                                                                                                                                                                    
                self.auto_timer=pygame.time.get_ticks()+AUTO_ROUND_MS; return True
                                                                                                                                                  
        return False
                                                                                                                                                      
    def live_pts(self,p):
                                                                                                                                                                          
        """Return current in-round points for player `p`."""
                                                                                                                                                  
        return self.tricks_won[p]*5+card_points(self.cards_won[p])

                                                                   

                                                                                                                                                  
class Renderer:
                                                                                                                                                                      
    """Resolution-independent UI renderer for cards, boards, and overlays."""
                                                                                                                                                      
    def __init__(self,screen):
                                                                                                                                                                          
        self.screen=screen; self.scale=1.0; self.scale_x=1.0; self.scale_y=1.0; self.ox=0; self.oy=0; self._fc={}
        self.card_back_img=None
        self._card_back_cache={}
                                                                                                                                                      
    def update_scale(self,sw,sh):
                                                                                                                                                                          
        """Recompute virtual-to-screen transform for current window size."""
                                                                                  
                                                                                 
        self.scale_x=max(0.001, sw/max(1.0, float(VW)))
        self.scale_y=max(0.001, sh/max(1.0, float(VH)))
        self.scale=min(self.scale_x, self.scale_y)
        self.ox=0.0; self.oy=0.0
        self._card_back_cache.clear()

    def set_card_back_texture(self, image_path):
        """Load external card-back texture used by all face-down cards."""
        self.card_back_img=None
        self._card_back_cache.clear()
        if not image_path or not os.path.exists(image_path):
            return False
        try:
            img=pygame.image.load(image_path)
            self.card_back_img=img.convert_alpha() if img.get_alpha() is not None else img.convert()
            return True
        except Exception:
            self.card_back_img=None
            return False

    def _scaled_card_back(self, w, h):
        """Return cached scaled texture for requested card-back size."""
        if self.card_back_img is None:
            return None
        key=(max(1, int(w)), max(1, int(h)))
        if key not in self._card_back_cache:
            self._card_back_cache[key]=pygame.transform.smoothscale(self.card_back_img, key)
        return self._card_back_cache[key]

    def _draw_back_rect(self, sr, rad):
        """Draw one face-down card rectangle, textured when available."""
        tex=self._scaled_card_back(sr.w, sr.h)
        if tex is None:
            pygame.draw.rect(self.screen,CARD_BACK,sr,border_radius=rad)
            inner=sr.inflate(-self.s(12),-self.s(12))
            if inner.w>0 and inner.h>0:
                pygame.draw.rect(self.screen,CARD_BACK2,inner,border_radius=max(2,self.s(6)))
        else:
            back=tex.copy()
            mask=pygame.Surface((sr.w,sr.h),pygame.SRCALPHA)
            pygame.draw.rect(mask,(255,255,255,255),mask.get_rect(),border_radius=rad)
            back.blit(mask,(0,0),special_flags=pygame.BLEND_RGBA_MULT)
            self.screen.blit(back,sr.topleft)
        pygame.draw.rect(self.screen,GOLD_DIM,sr,max(1,self.s(2)),border_radius=rad)

    def draw_card_back(self, vx, vy, vw=BASE_CW, vh=BASE_CH, corner=10):
        """Draw one card back at virtual coordinates and return screen rect."""
        sr=self.r(vx,vy,vw,vh)
        self._draw_back_rect(sr,max(2,self.s(corner)))
        return sr
                                                                                                                                                      
    def s(self,v):
                                                                                                                                                                          
        """Scale one virtual scalar to screen pixels."""
                                                                                                                                                  
        return max(1,round(v*self.scale))
                                                                                                                                                      
    def p(self,x,y):
                                                                                                                                                                          
        """Map one virtual point to screen coordinates."""
                                                                                                                                                  
        return(round(x*self.scale_x+self.ox),round(y*self.scale_y+self.oy))
                                                                                                                                                      
    def r(self,x,y,w,h):
                                                                                                                                                                          
        """Map virtual rectangle to a pygame.Rect in screen space."""
                                                                                                                                                  
        return pygame.Rect(round(x*self.scale_x+self.ox),round(y*self.scale_y+self.oy),
                                                                                                                                                                               
                           max(1,round(w*self.scale_x)),max(1,round(h*self.scale_y)))
                                                                                                                                                      
    def virt(self,sx,sy):
                                                                                                                                                                          
        """Map screen point back into virtual coordinate space."""
                                                                                                                                                  
        return((sx-self.ox)/max(self.scale_x,.001),(sy-self.oy)/max(self.scale_y,.001))
                                                                                                                                                      
    def font(self,name,size):
                                                                                                                                                                          
        """Return cached scaled font for consistent rendering performance."""
                                                                                                                                                                       
        text_scale=1.0 if name in ("card","card_sm","card_suit") else UI_TEXT_SCALE
        key=(name,max(8,round(size*text_scale*self.scale)))
                                                                                                                                                                    
        if key not in self._fc:
                                                                                                                                                                              
            self._fc[key]=pygame.font.SysFont("dejavusans,arial,segoeui",key[1],
                                                                                                                                                                                                              
                                               bold=(name in("title","ui_lg","bold")))
                                                                                                                                                  
        return self._fc[key]

                                                                                                                                                      
    def draw_felt(self,sw,sh):
                                                                                                                                                                          
        """Draw felt table background with subtle striping."""
                                                                                                                                                            
        self.screen.fill(FELT)
                                                                                                                                                                       
        step=max(4,self.s(6))
                                                                                                                                                                      
        for y in range(0,sh,step):
                                                                                                                                                                           
            c=FELT_DARK if(y//step)%2==0 else FELT
                                                                                                                                                                
            pygame.draw.line(self.screen,c,(0,y),(sw,y))

                                                                                                                                                      
    def draw_card(self,card,vx,vy,face_up=True,selected=False,dimmed=False,
                                                                                                                                                                                 
                  hover=False,trump_suit=None):
                                                                                                                                                            
        """Draw a single card (face-up or back) and return its screen rect."""
                                                                                                                                                                       
        sr=self.r(vx,vy,BASE_CW,BASE_CH); rad=max(2,self.s(10))
        text_scale=CARD_TEXT_SCALE
        s2=lambda v: self.s(v*text_scale)
        fs=lambda v: max(8, int(round(v*text_scale)))
                                                                                                                                                                    
        if not face_up:
            return self.draw_card_back(vx,vy,BASE_CW,BASE_CH,10)
                                                                                                                                                                       
        bg=(200,255,200) if selected else CARD_BG
                                                                                                                                                            
        pygame.draw.rect(self.screen,bg,sr,border_radius=rad)
                    
                                                                                                                                                                    
        if trump_suit and card.suit==trump_suit:
                                                                                                                                                                                                                                               
            tint=pygame.Surface((sr.w,sr.h),pygame.SRCALPHA)
                                                                                                                                                                
            pygame.draw.rect(tint,TRUMP_TINT,tint.get_rect(),border_radius=rad)
                                                                                                                                                                
            self.screen.blit(tint,sr.topleft)
                                                                                                                                                            
        pygame.draw.rect(self.screen,(180,180,180),sr,max(1,self.s(1)),border_radius=rad)
                                                                                                                                                                    
        if hover and not selected:
                                                                                                                                                                                                                                               
            hs=pygame.Surface((sr.w,sr.h),pygame.SRCALPHA)
                                                                                                                                                                
            pygame.draw.rect(hs,(255,255,200,50),hs.get_rect(),border_radius=rad)
                                                                                                                                                                
            self.screen.blit(hs,sr.topleft)
                                                                                                                                                                       
        col=SUIT_COLOUR[card.suit]
        rank_txt=rank_ui_text(card.rank)
        rank_corner=self.font("card",fs(28)).render(rank_txt,True,col)
        suit_corner=self.font("card_sm",fs(20)).render(card.suit,True,col)
        self.screen.blit(rank_corner,(sr.x+s2(8),sr.y+s2(6)))
                                                                                                                                                            
        self.screen.blit(suit_corner,(sr.x+s2(8),sr.y+s2(36)))
        rank_corner_br=pygame.transform.rotate(rank_corner,180)
        suit_corner_br=pygame.transform.rotate(suit_corner,180)
        self.screen.blit(rank_corner_br,rank_corner_br.get_rect(bottomright=(sr.right-s2(8),sr.bottom-s2(6))))
        self.screen.blit(suit_corner_br,suit_corner_br.get_rect(bottomright=(sr.right-s2(8),sr.bottom-s2(36))))
        if card.rank in COURT_SYMBOL:
            big=self.font("card_suit",fs(62)).render(rank_txt,True,col)
            self.screen.blit(big,big.get_rect(center=(sr.x+sr.w//2,sr.y+sr.h//2-s2(4))))
            suit_mark=self.font("card",fs(32)).render(card.suit,True,col)
            self.screen.blit(suit_mark,suit_mark.get_rect(center=(sr.x+sr.w//2,sr.y+sr.h//2+s2(38))))
        else:
            big=self.font("card_suit",fs(52)).render(card.suit,True,col)
            self.screen.blit(big,big.get_rect(center=(sr.x+sr.w//2,sr.y+sr.h//2+s2(10))))
                    
                                                                                                                                                                    
        if trump_suit and card.suit==trump_suit:
                                                                                                                                                                           
            sf=self.font("card_sm",fs(16)); star=sf.render("\u2605",True,(180,140,255))
                                                                                                                                                                
            self.screen.blit(star,(sr.x+s2(6),sr.y+sr.h-s2(24)))
                                                                                                                                                                    
        if dimmed:
                                                                                                                                                                                                                                               
            ds=pygame.Surface((sr.w,sr.h),pygame.SRCALPHA)
                                                                                                                                                                
            pygame.draw.rect(ds,DIM_OVERLAY,ds.get_rect(),border_radius=rad)
                                                                                                                                                                
            self.screen.blit(ds,sr.topleft)
                                                                                                                                                  
        return sr

                                                                                                                                                      
    def draw_hand(self,hand,vy,valid_indices=None,selected_indices=None,
                                                                                                                                                                                 
                  vmouse=None,hidden=False,trump_suit=None):
                                                                                                                                                                          
        """Draw fanned hand row and return clickable rect/index mappings."""
                                                                                                                                                                    
        if not hand: return []
                                                                                                                                                                       
        n=len(hand); overlap=min(88,max(38,int((VW-580-BASE_CW)/max(n-1,1))))
                                                                                                                                                                       
        total_w=(n-1)*overlap+BASE_CW; start_x=(VW-total_w)/2; rects=[]
                                                                                                                                                                      
        for i,card in enumerate(hand):
                                                                                                                                                                           
            cx=start_x+i*overlap; cy=vy
                                                                                                                                                                           
            dim=valid_indices is not None and i not in valid_indices
                                                                                                                                                                           
            sel=selected_indices is not None and i in selected_indices
                                                                                                                                                                           
            hov=False
                                                                                                                                                                        
            if not hidden and vmouse and not dim:
                                                                                                                                                                               
                hw=overlap if i<n-1 else BASE_CW
                                                                                                                                                                            
                if cx<=vmouse[0]<=cx+hw and cy<=vmouse[1]<=cy+BASE_CH: hov=True; cy-=18
                                                                                                                                                                           
            sr=self.draw_card(card,cx,cy,face_up=not hidden,selected=sel,dimmed=dim,
                                                                                                                                                                                              
                               hover=hov,trump_suit=trump_suit if not hidden else None)
                                                                                                                                                                           
            hw=overlap if i<n-1 else BASE_CW
                                                                                                                                                                           
            vrect=self.r(start_x+i*overlap,vy-(18 if hov else 0),hw,BASE_CH+(18 if hov else 0))
                                                                                                                                                                
            rects.append((vrect,i))
                                                                                                                                                  
        return rects

                                                                                                                                                      
    def draw_piles_row(self,piles,vy,valid_indices=None,vmouse=None,trump_suit=None):
                                                                                                                                                                          
        """Draw a player's 4 piles with top-card visibility/validity cues."""
                                                                                                                                                                       
        spacing=168; total_w=4*BASE_CW+3*spacing; start_x=(VW-total_w)/2; rects=[]
                                                                                                                                                                      
        for i,pile in enumerate(piles):
                                                                                                                                                                           
            px=start_x+i*(BASE_CW+spacing)
                                                                                                                                                                        
            if not pile:
                                                                                                                                                                               
                sr=self.r(px,vy,BASE_CW,BASE_CH)
                                                                                                                                                                    
                pygame.draw.rect(self.screen,FELT_DARK,sr,max(1,self.s(2)),border_radius=max(2,self.s(10)))
                                                                                                                                                               
                continue
            hidden_count=0
            if len(pile)>1:
                if pile[-1].face_up:
                    hidden_count=sum(1 for c in pile[:-1] if not c.face_up)
                else:
                    hidden_count=len(pile)-1
            visible_hidden=min(hidden_count, 12)
            for off in range(visible_hidden,0,-1):
                self.draw_card_back(px-off*6,vy-off*6,BASE_CW,BASE_CH,10)
            if hidden_count>visible_hidden:
                badge=self.font("ui_sm",15).render(f"+{hidden_count-visible_hidden}",True,WHITE)
                self.screen.blit(badge,self.p(px-30,vy-14))
                                                                                                                                                                           
            sr=self.draw_card(pile[-1],px,vy,face_up=pile[-1].face_up,trump_suit=trump_suit)
                                                                                                                                                                           
            valid=valid_indices is None or i in valid_indices
                                                                                                                                                                        
            if valid and vmouse:
                                                                                                                                                                               
                smp=self.p(vmouse[0],vmouse[1])
                                                                                                                                                                            
                if sr.collidepoint(smp):
                                                                                                                                                                                                                                                       
                    hs=pygame.Surface((sr.w,sr.h),pygame.SRCALPHA)
                                                                                                                                                                        
                    pygame.draw.rect(hs,(255,255,200,60),hs.get_rect(),border_radius=max(2,self.s(10)))
                                                                                                                                                                        
                    self.screen.blit(hs,sr.topleft)
                                                                                                                                                                        
            if not valid:
                                                                                                                                                                                                                                                   
                ds=pygame.Surface((sr.w,sr.h),pygame.SRCALPHA)
                                                                                                                                                                    
                pygame.draw.rect(ds,DIM_OVERLAY,ds.get_rect(),border_radius=max(2,self.s(10)))
                                                                                                                                                                    
                self.screen.blit(ds,sr.topleft)
                                                                                                                                                                
            rects.append((sr,i))
                                                                                                                                                  
        return rects

                                                                                                                                                      
    def draw_trick_area(self,trick_cards,trump_suit=None):
                                                                                                                                                                          
        """Draw currently played trick cards in table center."""
                                                                                                                                                                       
        cx,cy=VW/2,VH/2; n=len(trick_cards)
                                                                                                                                                                    
        if n==0: return
                                                                                                                                                                       
        gap=26; total=n*BASE_CW+(n-1)*gap; sx=cx-total/2
                                                                                                                                                                       
        labs={0:"Hand",1:"Hand",2:"Pile",3:"Pile"}
                                                                                                                                                                      
        for i,(card,pl) in enumerate(trick_cards):
                                                                                                                                                                           
            px=sx+i*(BASE_CW+gap); py=cy-BASE_CH/2
                                                                                                                                                                
            self.draw_card(card,px,py,True,trump_suit=trump_suit)
                                                                                                                                                                           
            col=GOLD if pl==0 else AI_THINK
                                                                                                                                                                           
            lbl=self.font("ui_sm",18).render(f"{'A' if pl==0 else 'B'}-{labs.get(i,'?')}",True,col)
                                                                                                                                                                
            self.screen.blit(lbl,lbl.get_rect(center=self.p(px+BASE_CW/2,py+BASE_CH+14)))

                                                                                                                                                      
    def draw_trick_piles(self,count,vx,vy,label):
                                                                                                                                                                          
        """Draw compact captured-tricks stack with count badge."""
                                                                                                                                                                    
        if count<=0: return
                                                                                                                                                                       
        tw=round(BASE_CW*.5); th=round(BASE_CH*.5)
                                                                                                                                                                      
        for i in range(min(count,5)):
            self.draw_card_back(vx+i*5,vy-i*4,tw,th,6)
                                                                                                                                                            
        self.screen.blit(self.font("bold",22).render(str(count),True,WHITE),self.p(vx+tw+10,vy-6))
                                                                                                                                                            
        self.screen.blit(self.font("ui_sm",16).render(label,True,(170,170,170)),self.p(vx,vy+th+10))

    def draw_contract_progress(self, vx, vy, bidder_points, bidder_target, defender_points, defender_target,
                               bidder_label="Bidder", defender_label="Defender"):
        """Draw bidder/defender round-target progress circles."""
        radius=max(16, self.s(24))
        gap=max(26, self.s(78))
        fill=(245,210,92)
        face=(26,26,26)
        ring=(212,188,118)
        txt_col=(235,235,220)
        sub_col=(190,190,175)

        def _draw_one(cx, cy, points, target, label):
            p=max(0, _to_int(points, 0))
            t=max(0, _to_int(target, 0))
            ratio=0.0 if t<=0 else max(0.0, min(1.0, float(p)/float(t)))
            pygame.draw.circle(self.screen, face, (cx, cy), radius)
            if ratio>0.0:
                start=-math.pi/2.0
                end=start+2.0*math.pi*ratio
                steps=max(16, int(76*ratio))
                pts=[(cx, cy)]
                for i in range(steps+1):
                    a=start+(end-start)*(i/steps)
                    pts.append((cx+int(math.cos(a)*radius), cy+int(math.sin(a)*radius)))
                if len(pts)>=3:
                    pygame.draw.polygon(self.screen, fill, pts)
            pygame.draw.circle(self.screen, ring, (cx, cy), radius, max(1, self.s(2)))
            frac=f"{p}/{t if t>0 else '-'}"
            lf=self.font("ui_sm",12)
            ff=self.font("bold",14)
            ls=lf.render(label, True, sub_col)
            fs=ff.render(frac, True, txt_col)
            self.screen.blit(ls, ls.get_rect(center=(cx, cy-radius-self.s(12))))
            self.screen.blit(fs, fs.get_rect(center=(cx, cy+radius+self.s(12))))

        lcx,lcy=self.p(vx, vy)
        rcx=lcx+gap
        _draw_one(lcx, lcy, bidder_points, bidder_target, bidder_label)
        _draw_one(rcx, lcy, defender_points, defender_target, defender_label)

                                                                                                                                                      
    def draw_turn_marker(self,ap,tick):
                                                                                                                                                                          
        """Draw animated active-player marker chip."""
                                                                                                                                                                    
        if ap is None: return
                                                                                                                                                                       
        bounce=math.sin(tick*.005)*8; vx=245
                                                                                                                                                                       
        vy=(VH-300+bounce) if ap==0 else (225+bounce)
                                                                                                                                                                       
        cx_s,cy_s=self.p(vx,vy); chip_r=self.s(28)
                                                                                                                                                                       
        pulse=0.5+0.5*math.sin(tick*0.006)
                                                                                                                                                                       
        glow_r=chip_r+self.s(int(8+6*pulse))
                                                                                                                                                                       
        gc=(int(255*pulse),int(200*pulse),int(50*pulse))
                                                                                                                                                            
        pygame.draw.circle(self.screen,gc,(cx_s,cy_s),glow_r)
                                                                                                                                                            
        pygame.draw.circle(self.screen,(20,20,20),(cx_s,cy_s),chip_r)
                                                                                                                                                            
        pygame.draw.circle(self.screen,(80,80,80),(cx_s,cy_s),chip_r,max(2,self.s(3)))
                                                                                                                                                                       
        lt=self.font("bold",18).render(HUMAN_NAME.upper() if ap==HUMAN else AI_NAME.upper(),True,GOLD)
                                                                                                                                                            
        self.screen.blit(lt,lt.get_rect(center=(cx_s,cy_s)))

                                                                                                                                                      
    def draw_analog_clock(self,clock,tick):
                                                                                                                                                                          
        """Render dual analog countdown clocks for both players."""
                                                                                                                                                                       
        face_r=91; cx_a=142; cx_b=VW-142; cy=VH//2
                                                                                                                                                                      
        for pl,cx_v in [(HUMAN,cx_a),(AI_PLAYER,cx_b)]:
                                                                                                                                                                           
            active=clock.active==pl; low=clock.rem[pl]<60
                                                                                                                                                                           
            cx_s,cy_s=self.p(cx_v,cy); sr=self.s(face_r)
                                                                                                                                                                           
            body_r=self.r(cx_v-face_r-20,cy-face_r-46,face_r*2+40,face_r*2+72)
                                                                                                                                                                           
            wood=(70,45,25) if active else (55,35,20)
                                                                                                                                                                
            pygame.draw.rect(self.screen,wood,body_r,border_radius=max(2,self.s(16)))
                                                                                                                                                                
            pygame.draw.rect(self.screen,(90,60,30),body_r,max(1,self.s(3)),border_radius=max(2,self.s(16)))
                                                                                                                                                                           
            btn_w,btn_h=self.s(52),self.s(18)
                                                                                                                                                                           
            btn_y=body_r.y-btn_h+self.s(3 if not active else 10)
                                                                                                                                                                
            pygame.draw.rect(self.screen,(40,40,40) if active else (80,80,80),
                                                                                                                                                                                 
                             pygame.Rect(cx_s-btn_w//2,btn_y,btn_w,btn_h),border_radius=max(2,self.s(5)))
                                                                                                                                                                           
            face_col=(255,220,220) if low else (240,235,220)
                                                                                                                                                                
            pygame.draw.circle(self.screen,face_col,(cx_s,cy_s),sr)
                                                                                                                                                                           
            rim=GOLD if active else (120,100,70)
                                                                                                                                                                
            pygame.draw.circle(self.screen,rim,(cx_s,cy_s),sr,max(2,self.s(4)))
                                                                                                                                                                          
            for m in range(60):
                                                                                                                                                                               
                a=math.radians(m*6-90)
                                                                                                                                                                               
                r1=sr-(self.s(5) if m%5==0 else self.s(3))
                                                                                                                                                                               
                r2=sr-(self.s(13) if m%5==0 else self.s(8))
                                                                                                                                                                    
                pygame.draw.line(self.screen,(60,60,60),
                                                                                                                                                                        
                    (cx_s+int(r1*math.cos(a)),cy_s+int(r1*math.sin(a))),
                                                                                                                                                                        
                    (cx_s+int(r2*math.cos(a)),cy_s+int(r2*math.sin(a))),
                                                                                                                                                                        
                    max(1,self.s(2 if m%5==0 else 1)))
                                                                                                                                                                          
            for h in range(1,13):
                                                                                                                                                                               
                a=math.radians(h*30-90)
                                                                                                                                                                               
                nx=cx_s+int((sr-self.s(28))*math.cos(a))
                                                                                                                                                                               
                ny=cy_s+int((sr-self.s(28))*math.sin(a))
                                                                                                                                                                               
                nt=self.font("ui_sm",15).render(str(h),True,(60,60,60))
                                                                                                                                                                    
                self.screen.blit(nt,nt.get_rect(center=(nx,ny)))
                                                                                                                                                                           
            ts=max(0,clock.rem[pl]); mins=ts/60.0; secs=ts%60
                                                                                                                                                                           
            ma=math.radians(mins*6-90); ml=sr-self.s(36)
                                                                                                                                                                
            pygame.draw.line(self.screen,(30,30,30),(cx_s,cy_s),
                                                                                                                                                                    
                (cx_s+int(ml*math.cos(ma)),cy_s+int(ml*math.sin(ma))),max(2,self.s(4)))
                                                                                                                                                                           
            sa=math.radians(secs*6-90); sl=sr-self.s(20)
                                                                                                                                                                
            pygame.draw.line(self.screen,(200,30,30) if low else (180,50,50),(cx_s,cy_s),
                                                                                                                                                                    
                (cx_s+int(sl*math.cos(sa)),cy_s+int(sl*math.sin(sa))),max(1,self.s(2)))
                                                                                                                                                                
            pygame.draw.circle(self.screen,(40,40,40),(cx_s,cy_s),max(2,self.s(5)))
                                                                                                                                                                           
            dt=self.font("bold",20).render(clock.fmt(pl),True,WHITE)
                                                                                                                                                                
            self.screen.blit(dt,dt.get_rect(center=(cx_s,body_r.bottom-self.s(18))))
                                                                                                                                                                           
            lt=self.font("ui_sm",18).render(HUMAN_NAME if pl==HUMAN else AI_NAME,True,GOLD if active else (140,140,140))
                                                                                                                                                                
            self.screen.blit(lt,lt.get_rect(center=(cx_s,body_r.bottom+self.s(18))))
                                                                                                                                                                        
            if clock.flagged[pl]:
                                                                                                                                                                               
                ft=self.font("ui_lg",26).render("TIME!",True,(255,50,50))
                                                                                                                                                                    
                self.screen.blit(ft,ft.get_rect(center=(cx_s,body_r.bottom+self.s(44))))

                                                                                                                                                      
    def draw_chips(self,amount,vx,vy,label):
                                                                                                                                                                          
        """Draw chip stack decomposition for a dollar amount."""
                                                                                                                                                                       
        tcol=(255,95,95) if amount<0 else GOLD
        lt=self.font("bold",18).render(f"{label}: {money_text(amount)}",True,tcol)
                                                                                                                                                            
        self.screen.blit(lt,self.p(vx,vy-28))
                                                                                                                                                                    
        if amount<=0: return
                                                                                                                                                                       
        denoms=[100,50,20,10,5]; chips={}; rem=abs(amount)
                                                                                                                                                                      
        for d in denoms: chips[d]=rem//d; rem=rem%d
                                                                                                                                                                       
        chip_r=21; x_off=0
                                                                                                                                                                      
        for d in denoms:
                                                                                                                                                                           
            cnt=chips[d]
                                                                                                                                                                        
            if cnt==0: continue
                                                                                                                                                                          
            for j in range(min(cnt,5)):
                                                                                                                                                                               
                ccy=vy+26-j*6; scx,scy=self.p(vx+x_off+chip_r,ccy); scr=self.s(chip_r)
                                                                                                                                                                    
                pygame.draw.circle(self.screen,CHIP_EDGE[d],(scx,scy+self.s(3)),scr)
                                                                                                                                                                    
                pygame.draw.circle(self.screen,CHIP_COLS[d],(scx,scy),scr)
                                                                                                                                                                    
                pygame.draw.circle(self.screen,CHIP_EDGE[d],(scx,scy),scr-self.s(4),max(1,self.s(1)))
                                                                                                                                                                               
                dt=self.font("card_sm",11).render(str(d),True,WHITE if d>=10 else(40,40,40))
                                                                                                                                                                    
                self.screen.blit(dt,dt.get_rect(center=(scx,scy)))
                                                                                                                                                                        
            if cnt>5:
                                                                                                                                                                               
                bt=self.font("card_sm",12).render(f"x{cnt}",True,WHITE)
                                                                                                                                                                    
                self.screen.blit(bt,bt.get_rect(center=self.p(vx+x_off+chip_r,vy-2)))
                                                                                                                                                                              
            x_off+=chip_r*2+13

                                                                                                                                                      
    def draw_live_score(self,game,vx,vy,player):
                                                                                                                                                                          
        """Draw current round points/tricks panel for one player."""
                                                                                                                                                                       
        pn=HUMAN_NAME if player==HUMAN else AI_NAME; pts=game.live_pts(player)
                                                                                                                                                                       
        pw,ph=280,135; sr=self.r(vx,vy,pw,ph)
                                                                                                                                                                                                                                           
        bg=pygame.Surface((sr.w,sr.h),pygame.SRCALPHA); bg.fill((0,0,0,140))
                                                                                                                                                            
        self.screen.blit(bg,sr.topleft)
                                                                                                                                                            
        pygame.draw.rect(self.screen,GOLD_DIM,sr,max(1,self.s(2)),border_radius=max(2,self.s(8)))
                                                                                                                                                            
        self.screen.blit(self.font("bold",20).render(f"{pn}: ${pts}",True,GOLD),self.p(vx+10,vy+8))
                                                                                                                                                                       
        vc=count_value(game.cards_won[player])
                                                                                                                                                            
        self.screen.blit(self.font("ui_sm",16).render(
                                                                                                                                                                
            f"5\u00d7{vc['5']}  10\u00d7{vc['10']}  A\u00d7{vc['A']}",True,WHITE),self.p(vx+10,vy+38))
                                                                                                                                                            
        self.screen.blit(self.font("ui_sm",14).render(
                                                                                                                                                                
            f"Tricks: {game.tricks_won[player]} (${game.tricks_won[player]*5})",True,(180,180,180)),
                                                                                                                                                                
            self.p(vx+10,vy+62))
                                                                                                                                                                    
        if game.bid_winner==player:
                                                                                                                                                                           
            failing=pts<game.bid_amount
                                                                                                                                                                           
            tc=(255,80,80) if failing else (80,255,80)
                                                                                                                                                                
            self.screen.blit(self.font("bold",16).render(f"TARGET: ${game.bid_amount}",True,tc),
                                                                                                                                                                                 
                             self.p(vx+10,vy+88))
                                                                                                                                                                           
            bar=self.r(vx+10,vy+112,pw-20,14)
                                                                                                                                                                
            pygame.draw.rect(self.screen,(40,40,40),bar,border_radius=max(2,self.s(4)))
                                                                                                                                                                           
            pct=min(1.0,pts/max(1,game.bid_amount))
                                                                                                                                                                           
            fill=pygame.Rect(bar.x,bar.y,max(1,int(bar.w*pct)),bar.h)
                                                                                                                                                                
            pygame.draw.rect(self.screen,tc,fill,border_radius=max(2,self.s(4)))

                                                                                                                                                      
    def draw_card_history(self,tracker,vx,vy,vw,vh,trump_suit):
                                                                                                                                                                          
        """Draw scrollable card history overlay."""
                                                                                                                                                                       
        sr=self.r(vx,vy,vw,vh)
                                                                                                                                                                                                                                           
        bg=pygame.Surface((sr.w,sr.h),pygame.SRCALPHA); bg.fill((0,0,0,200))
                                                                                                                                                            
        self.screen.blit(bg,sr.topleft)
                                                                                                                                                            
        pygame.draw.rect(self.screen,GOLD,sr,max(1,self.s(2)),border_radius=max(2,self.s(10)))
                                                                                                                                                            
        self.screen.blit(self.font("bold",20).render("Card History",True,GOLD),self.p(vx+10,vy+8))
                                                                                                                                                                       
        tricks=tracker.all_tricks()
                                                                                                                                                                       
        y_off=44; mini_w=96; mini_h=138
                                                                                                                                                                      
        for ti,trick in enumerate(tricks):
                                                                                                                                                                           
            tx=vx+10; ty=vy+y_off
                                                                                                                                                                        
            if ty+mini_h+20>vy+vh: break
                                                                                                                                                                
            self.screen.blit(self.font("ui_sm",15).render(f"T{ti+1}:",True,(180,180,180)),self.p(tx,ty))
                                                                                                                                                                          
            for ci,(card,pl) in enumerate(trick):
                                                                                                                                                                               
                cx=tx+40+ci*(mini_w+6); cy_c=ty-4
                                                                                                                                                                               
                mini_sr=self.r(cx,cy_c,mini_w,mini_h)
                                                                                                                                                                               
                card_bg=CARD_BG
                                                                                                                                                                    
                pygame.draw.rect(self.screen,card_bg,mini_sr,border_radius=max(2,self.s(4)))
                                                                                                                                                                            
                if trump_suit and card.suit==trump_suit:
                                                                                                                                                                                                                                                       
                    ts=pygame.Surface((mini_sr.w,mini_sr.h),pygame.SRCALPHA)
                                                                                                                                                                        
                    pygame.draw.rect(ts,TRUMP_TINT,ts.get_rect(),border_radius=max(2,self.s(4)))
                                                                                                                                                                        
                    self.screen.blit(ts,mini_sr.topleft)
                                                                                                                                                                    
                pygame.draw.rect(self.screen,(160,160,160),mini_sr,max(1,self.s(1)),border_radius=max(2,self.s(4)))
                                                                                                                                                                               
                sc=SUIT_COLOUR[card.suit]
                                                                                                                                                                               
                rf=self.font("bold",24)
                                                                                                                                                                    
                self.screen.blit(rf.render(card_ui_text(card),True,sc),
                                                                                                                                                                                     
                                 (mini_sr.x+self.s(6),mini_sr.y+self.s(6)))
                                                                                                                                                                               
                pf=self.font("card_sm",13)
                                                                                                                                                                               
                plbl="A" if pl==0 else "B"
                                                                                                                                                                    
                self.screen.blit(pf.render(plbl,True,GOLD if pl==0 else AI_THINK),
                                                                                                                                                                                     
                                 (mini_sr.x+self.s(3),mini_sr.bottom-self.s(14)))
                                                                                                                                                                              
            y_off+=mini_h+8

                                                                                                                                                      
    def draw_toggle_btn(self,vx,vy,vmouse,showing,label):
                                                                                                                                                                          
        """Draw overlay toggle button and return clickable rect."""
                                                                                                                                                                       
        sr=self.r(vx,vy,190,54)
                                                                                                                                                                       
        col=(80,80,80) if showing else BTN_NORMAL
                                                                                                                                                                    
        if vmouse:
                                                                                                                                                                           
            sp=self.p(vmouse[0],vmouse[1])
                                                                                                                                                                        
            if sr.collidepoint(sp): col=BTN_HOVER
                                                                                                                                                            
        pygame.draw.rect(self.screen,col,sr,border_radius=max(2,self.s(8)))
                                                                                                                                                            
        pygame.draw.rect(self.screen,GOLD_DIM,sr,max(1,self.s(2)),border_radius=max(2,self.s(8)))
                                                                                                                                                                       
        txt=label if not showing else "\u2716 Close"
                                                                                                                                                            
        self.screen.blit(self.font("ui_sm",16).render(txt,True,BTN_TEXT),
                                                                                                                                                                             
                         self.font("ui_sm",16).render(txt,True,BTN_TEXT).get_rect(center=sr.center))
                                                                                                                                                  
        return sr

                                                                                                                                                      
    def draw_played_cards(self,tracker,vx,vy,vw,vh):
                                                                                                                                                                          
        """Draw played cards grouped into four suit rows."""
                                                                                                                                                                       
        sr=self.r(vx,vy,vw,vh)
        bg=pygame.Surface((sr.w,sr.h),pygame.SRCALPHA); bg.fill((255,255,255,238))
                                                                                                                                                            
        self.screen.blit(bg,sr.topleft)
                                                                                                                                                            
        pygame.draw.rect(self.screen,(80,80,80),sr,max(1,self.s(2)),border_radius=max(2,self.s(10)))
                                                                                                                                                            
        self.screen.blit(self.font("bold",20).render("Played Cards",True,(40,40,40)),self.p(vx+10,vy+8))
                                                                                                                                                                       
        rows=tracker.played_by_suit()
                                                                                                                                                                       
        y=vy+40
                                                                                                                                                                      
        for s in SUITS:
                                                                                                                                                                           
            line=f"{s}: " + " ".join(card_ui_text(c) for c in sorted(rows[s], key=lambda c:RANK_ORDER[c.rank]))
                                                                                                                                                                           
            col=SUIT_COLOUR[s]
                                                                                                                                                                
            self.screen.blit(self.font("ui_sm",18).render(line if line.strip()!=f"{s}:" else f"{s}: -",True,col),self.p(vx+12,y))
                                                                                                                                                                              
            y+=28

                                                                                                                                                      
    def draw_ai_analysis(self,analysis,pv_lines,vx,vy,vw,vh):
                                                                                                                                                                          
        """Draw AI ranking panel with score breakdown and PV snippets."""
                                                                                                                                                                       
        sr=self.r(vx,vy,vw,vh)
                                                                                                                                                                                                                                           
        s=pygame.Surface((sr.w,sr.h),pygame.SRCALPHA); s.fill((0,0,0,170))
                                                                                                                                                            
        self.screen.blit(s,sr.topleft)
                                                                                                                                                            
        pygame.draw.rect(self.screen,GOLD_DIM,sr,max(1,self.s(2)),border_radius=max(2,self.s(10)))
                                                                                                                                                                                                                                                                      
        title=self.font("ui_sm",18).render(f"{AI_NAME} hybrid search",True,GOLD)
                                                                                                                                                            
        self.screen.blit(title,(sr.x+self.s(10),sr.y+self.s(8)))
                                                                                                                                                                       
        y=sr.y+self.s(34)
                                                                                                                                                                      
        for i,(label,ev,prob,samples,nodes) in enumerate(analysis):
            suit=next((s for s in SUITS if s in label), None)
            lcol=SUIT_COLOUR.get(suit, WHITE)
            prefix=f"{i+1}. "
            suffix=f" p={prob:>4.0%} EV={ev:>6.1f} s={int(samples):>3} n={int(nodes):>5}"
            px=sr.x+self.s(10)
            ptxt=self.font("ui_sm",16).render(prefix,True,WHITE)
            self.screen.blit(ptxt,(px,y))
            px+=ptxt.get_width()
            ltxt=self.font("ui_sm",16).render(label,True,lcol)
            lb=ltxt.get_rect(topleft=(px-self.s(2), y-self.s(1)))
            pygame.draw.rect(self.screen,(245,245,245),lb.inflate(self.s(6),self.s(2)),
                             border_radius=max(2,self.s(4)))
            self.screen.blit(ltxt,(px,y))
            px+=ltxt.get_width()+self.s(6)
            stxt=self.font("ui_sm",16).render(suffix,True,WHITE)
            self.screen.blit(stxt,(px,y))
                                                                                                                                                                
            y+=self.s(22)
                                                                                                                                                                    
        if pv_lines:
                                                                                                                                                                
            y+=self.s(6)
                                                                                                                                                                           
            pv_t=self.font("ui_sm",16).render("Most likely lines:",True,GOLD)
                                                                                                                                                                
            self.screen.blit(pv_t,(sr.x+self.s(10),y))
                                                                                                                                                                
            y+=self.s(20)
                                                                                                                                                                           
            font=self.font("ui_sm",16)
                                                                                                                                                                           
            max_w=sr.w-self.s(26)
                                                                                                                                                                           
            max_y=sr.bottom-self.s(10)
                                                                                                                                                                          
            for line in pv_lines:
                                                                                                                                                                               
                words=line.split(" ")
                                                                                                                                                                               
                rows=[]; cur=""
                                                                                                                                                                              
                for w in words:
                                                                                                                                                                                   
                    cand=(cur+" "+w).strip()
                                                                                                                                                                                
                    if cur and font.size(cand)[0]>max_w:
                                                                                                                                                                            
                        rows.append(cur); cur=w
                                                                                                                                                                                    
                        if len(rows)==2:
                                                                                                                                               
                            break
                                                                                                                                                               
                    else:
                                                                                                                                                                                       
                        cur=cand
                                                                                                                                                                            
                if len(rows)<2 and cur:
                                                                                                                                                                        
                    rows.append(cur)
                                                                                                                                                                            
                if len(rows)==2 and (" ".join(words)).strip()!=(" ".join(rows)).strip():
                                                                                                                                                                                
                    if not rows[1].endswith("..."):
                                                                                                                                                                            
                        rows[1]=(rows[1][:-3] if len(rows[1])>3 else rows[1])+"..."
                                                                                                                                                                              
                for r in rows[:2]:
                                                                                                                                                                                   
                    txt=font.render(r,True,(220,220,220))
                                                                                                                                                                        
                    self.screen.blit(txt,(sr.x+self.s(14),y))
                                                                                                                                                                        
                    y+=self.s(20)
                                                                                                                                                                                
                    if y>max_y: return
                                                                                                                                                                    
                y+=self.s(6)
                                                                                                                                                                            
                if y>max_y: return

                                                                                                                                                      
    def draw_button(self,text,vx,vy,vw,vh,vmouse=None,enabled=True):
                                                                                                                                                                          
        """Draw generic rounded UI button and return its rect."""
                                                                                                                                                                       
        sr=self.r(vx,vy,vw,vh); col=BTN_NORMAL
                                                                                                                                                                    
        if not enabled: col=(40,40,40)
                                                                                                                                                      
        elif vmouse and sr.collidepoint(*self.p(vmouse[0],vmouse[1])): col=BTN_HOVER
                                                                                                                                                                       
        rad=max(2,self.s(10))
                                                                                                                                                            
        pygame.draw.rect(self.screen,col,sr,border_radius=rad)
                                                                                                                                                            
        pygame.draw.rect(self.screen,GOLD_DIM,sr,max(1,self.s(2)),border_radius=rad)
                                                                                                                                                                       
        t=self.font("btn",26).render(text,True,BTN_TEXT if enabled else (100,100,100))
                                                                                                                                                            
        self.screen.blit(t,t.get_rect(center=sr.center)); return sr

                                                                                                                                                      
    def _suit_chunks(self,text,default_color):
        """Split text into chunks so suit symbols can be rendered in suit colors."""
        chunks=[]
        cur=""
        for ch in str(text):
            if ch in SUITS:
                if cur:
                    chunks.append((cur, default_color))
                    cur=""
                chunks.append((ch, SUIT_COLOUR.get(ch, default_color)))
            else:
                cur+=ch
        if cur or not chunks:
            chunks.append((cur, default_color))
        return chunks

    def _draw_chunks_left(self,font,chunks,sx,sy):
        """Draw pre-colored text chunks with left anchor in screen coordinates."""
        x=int(sx)
        y=int(sy)
        for seg,col in chunks:
            if not seg:
                continue
            surf=font.render(seg,True,col)
            self.screen.blit(surf,(x,y))
            x+=surf.get_width()

    def _draw_chunks_center(self,font,chunks,cx,cy):
        """Draw pre-colored text chunks centered around screen coordinates."""
        widths=[font.size(seg)[0] for seg,_ in chunks if seg]
        total_w=sum(widths)
        x=int(cx-total_w/2)
        y=int(cy-font.get_height()/2)
        self._draw_chunks_left(font,chunks,x,y)

                                                                                                                                                      
    def draw_text_center(self,text,vy,fname="ui",fsize=28,color=WHITE):
                                                                                                                                                                          
        """Render centered text in virtual coordinates."""
        font=self.font(fname,fsize)
        cx,cy=self.p(VW/2,vy)
        self._draw_chunks_center(font,self._suit_chunks(text,color),cx,cy)
                                                                                                                                                      
    def draw_text(self,text,vx,vy,fname="ui_sm",fsize=22,color=GOLD):
                                                                                                                                                                          
        """Render anchored text in virtual coordinates."""
        font=self.font(fname,fsize)
        sx,sy=self.p(vx,vy)
        self._draw_chunks_left(font,self._suit_chunks(text,color),sx,sy)

                                                                                                                                                      
    def draw_score_bar(self,game):
                                                                                                                                                                          
        """Draw bottom status bar with clocks plus live round/match breakdown."""
                                                                                                                                                                       
        bh=SCORE_BAR_H; bvy=VH-bh; sr=self.r(0,bvy,VW,bh)
                                                                                                                                                                                                                                           
        s=pygame.Surface((sr.w,sr.h),pygame.SRCALPHA); s.fill((255,255,255,138))
                                                                                                                                                            
        self.screen.blit(s,sr.topleft)
        pygame.draw.line(self.screen,(185,185,185),(sr.x,sr.y),(sr.right,sr.y),max(1,self.s(2)))
                                                                                                                                                          
        def _clock_col(pl):
                                                                                                                                                                        
            if game.clock.flagged[pl]: return (255,80,80)
                                                                                                                                                                        
            if game.clock.active==pl: return (150,122,50)
                                                                                                                                                                        
            if game.clock.rem[pl]<60: return (255,195,110)
                                                                                                                                                      
            return (45,45,45)
        pad=max(8,self.s(14))
        top_y=sr.y+self.s(14)
        ltxt=self.font("bold",20).render(f"{HUMAN_NAME} {game.clock.fmt(HUMAN)}",True,_clock_col(HUMAN))
        rtxt=self.font("bold",20).render(f"{AI_NAME} {game.clock.fmt(AI_PLAYER)}",True,_clock_col(AI_PLAYER))
        self.screen.blit(ltxt,ltxt.get_rect(midleft=(sr.x+pad,top_y)))
        self.screen.blit(rtxt,rtxt.get_rect(midright=(sr.right-pad,top_y)))
        parts=[f"Round {game.round_num}"]
        if game.trump_suit:
            parts.append(f"Trump {game.trump_suit}")
        if game.bid_winner is not None:
            parts.append(f"Bid {player_name(game.bid_winner)} ${game.bid_amount}")
        mid_txt="  |  ".join(parts)
        self._draw_chunks_center(self.font("score",20), self._suit_chunks(mid_txt, (74,60,28)), sr.centerx, top_y)

        def _panel(player, x, y, w, h, edge):
            rr=pygame.Rect(x,y,w,h)
            panel=pygame.Surface((rr.w,rr.h),pygame.SRCALPHA); panel.fill((255,255,255,110))
            self.screen.blit(panel, rr.topleft)
            pygame.draw.rect(self.screen,edge,rr,max(1,self.s(2)),border_radius=max(2,self.s(8)))
            pn=HUMAN_NAME if player==HUMAN else AI_NAME
            pts=game.live_pts(player)
            vc=count_value(game.cards_won[player])
            if game.bid_winner is None:
                target_txt="target -"
            elif game.bid_winner==player:
                bid_target=max(0, _to_int(game.bid_amount, 0))
                target_txt=f"target {money_text(bid_target)}"
            else:
                                          
                                                                           
                bid_target=max(0, _to_int(game.bid_amount, 0))
                defend_target=max(0, TOTAL_PTS-(bid_target-5))
                target_txt=f"bust {money_text(defend_target)}"
            info=(
                f"{pn}  round {money_text(pts)}  tricks {game.tricks_won[player]} ({money_text(game.tricks_won[player]*5)})  "
                f"5x{vc['5']} 10x{vc['10']} Ax{vc['A']}  match {money_text(game.scores[player])}/{money_text(game.match_target)}  {target_txt}"
            )
            chunks=self._suit_chunks(info, (30,30,30))
            self._draw_chunks_left(self.font("ui_sm",20), chunks, rr.x+self.s(10), rr.y+self.s(9))

        gap=self.s(14)
        box_y=sr.y+self.s(26)
        box_h=sr.h-self.s(33)
        box_w=(sr.w-gap*3)//2
        _panel(HUMAN, sr.x+gap, box_y, box_w, box_h, (150,122,50))
        _panel(AI_PLAYER, sr.x+gap*2+box_w, box_y, box_w, box_h, (65,110,185))
                                                                                                                                                      
    def draw_match_bar(self,game):
                                                                                                                                                                          
        """Draw top progress bars toward match target for both players."""
                                                                                                                                                                       
        bh=12; sr=self.r(0,0,VW,bh); pygame.draw.rect(self.screen,(20,20,20),sr)
                                                                                                                                                                       
        ra=max(0.0,min(1.0,game.scores[0]/max(1,game.match_target)))
        pw_a=int(sr.w*0.5*ra)
        if pw_a>0:
            pygame.draw.rect(self.screen,GOLD,pygame.Rect(sr.x,sr.y,pw_a,sr.h))
                                                                                                                                                                       
        rb=max(0.0,min(1.0,game.scores[1]/max(1,game.match_target)))
        pw_b=int(sr.w*0.5*rb)
        if pw_b>0:
            pygame.draw.rect(self.screen,AI_THINK,pygame.Rect(sr.x+sr.w-pw_b,sr.y,pw_b,sr.h))
    def draw_fireworks(self, tick, cx, cy, radius=420, bursts=6, spark_count=18):
        """Draw deterministic fireworks burst clusters for celebration overlays."""
        for b in range(max(1, int(bursts))):
            phase=(tick*0.0017*(1.0+0.1*b)+b*0.73)%1.0
            bx=cx+math.cos(tick*0.0009+b*1.31)*radius*0.55
            by=cy-120+math.sin(tick*0.0011+b*1.17)*radius*0.32
            core_col=(
                int(170+85*abs(math.sin(tick*0.002+b*0.9))),
                int(120+110*abs(math.sin(tick*0.0027+b*1.1))),
                int(120+110*abs(math.sin(tick*0.0032+b*1.3))),
            )
            pygame.draw.circle(self.screen,core_col,self.p(bx,by),max(2,self.s(7)))
            for k in range(max(8, int(spark_count))):
                a=(2*math.pi*k/max(1,spark_count))+phase*2*math.pi+b*0.33
                d=40+phase*150+(k%3)*8
                px=bx+math.cos(a)*d
                py=by+math.sin(a)*d
                c=(
                    int(140+110*abs(math.sin(a+b))),
                    int(110+120*abs(math.sin(a*1.3+b*0.7))),
                    int(120+100*abs(math.sin(a*1.7+b*0.5))),
                )
                pygame.draw.circle(self.screen,c,self.p(px,py),max(1,self.s(3)))
                                                                                                                                                      
    def draw_shelem(self,player,elapsed,tick,big=True):
                                                                                                                                                                          
        """Draw animated Shelem celebration overlay."""
                                                                                                                                                                         
        import colorsys
                                                                                                                                                                       
        cx,cy=VW/2,VH/2; t=elapsed/1000.0
                                                                                                                                                                       
        scale=1.0+0.3*math.sin(t*4); fsize=int(80*scale)
                                                                                                                                                                       
        label="BIG SHELEM!" if big else "Small Shelem!"
                                                                                                                                                                       
        txt=self.font("title",fsize).render(label,True,GOLD)
                                                                                                                                                                       
        hue=(tick*0.3)%360; r,g,b=colorsys.hsv_to_rgb(hue/360,0.8,1.0)
                                                                                                                                                                       
        gc=(int(r*255),int(g*255),int(b*255))
                                                                                                                                                                       
        gt=self.font("title",fsize+4).render(label,True,gc)
                                                                                                                                                            
        self.screen.blit(gt,gt.get_rect(center=self.p(cx,cy-60)))
                                                                                                                                                            
        self.screen.blit(txt,txt.get_rect(center=self.p(cx,cy-60)))
                                                                                                                                                                       
        pn=HUMAN_NAME if player==HUMAN else AI_NAME
                                                                                                                                                                       
        amt="$330" if big else "$215"
                                                                                                                                                                       
        wt=self.font("ui_lg",36).render(f"{pn} wins {amt}!",True,WHITE)
                                                                                                                                                            
        self.screen.blit(wt,wt.get_rect(center=self.p(cx,cy+30)))
        self.draw_fireworks(tick, cx, cy, radius=560, bursts=8, spark_count=22)
        praise_big=("Legendary contract.", "Masterclass execution.", "Unstoppable precision.")
        praise_small=("Beautiful sweep.", "Clinical finish.", "Outstanding control.")
        praise=praise_big if big else praise_small
        mood=praise[int((t*2.4)%len(praise))]
        mood_txt=self.font("ui",30).render(mood,True,(245,245,245))
        self.screen.blit(mood_txt,mood_txt.get_rect(center=self.p(cx,cy+95)))
                                                                                                                                                                      
        for i in range(12):
                                                                                                                                                                           
            a=math.radians(i*30+t*60); r2=120+40*math.sin(t*3+i)
                                                                                                                                                                           
            px=cx+r2*math.cos(a); py=cy-60+r2*math.sin(a)
                                                                                                                                                                           
            suit=SUITS[i%4]; sc=SUIT_COLOUR[suit]
                                                                                                                                                                           
            st=self.font("card_suit",30).render(suit,True,sc)
                                                                                                                                                                
            self.screen.blit(st,st.get_rect(center=self.p(px,py)))

                                                                   

                                                                                                                                                  
class ShelemApp:
                                                                                                                                                        
    """Top-level application controller (events, AI timing, rendering)."""
                                                                                                                                                      
    def __init__(self, replay_game_id=None, replay_state_num=1):
                                                                                                                                                                          
        """Initialize pygame, sound effects, renderer, AI, and UI state."""
                                                                                                                                                            
        pygame.init(); pygame.mixer.init(22050,-16,1,512)
        self.asset_paths={
            "card_back": os.path.join(ASSET_BASE_DIR, CARD_BACK_IMAGE_FILE),
            "payout": os.path.join(ASSET_BASE_DIR, PAYOUT_SOUND_FILE),
            "setup_music": os.path.join(ASSET_BASE_DIR, SETUP_MUSIC_FILE),
            "gameplay_music": os.path.join(ASSET_BASE_DIR, GAMEPLAY_MUSIC_FILE),
            "gameplay_music_alt": os.path.join(ASSET_BASE_DIR, GAMEPLAY_MUSIC_ALT_FILE),
            "danger_music": os.path.join(ASSET_BASE_DIR, DANGER_MUSIC_FILE),
            "requiem_music": os.path.join(ASSET_BASE_DIR, REQUIEM_MUSIC_FILE),
        }
                                                                                                                                                            
        self.card_snd=pygame.mixer.Sound(_wav(22050,0.08,_card_snd)); self.card_snd.set_volume(0.5)
                                                                                                                                                            
        self.chip_snd=pygame.mixer.Sound(_wav(22050,0.15,_chip_snd)); self.chip_snd.set_volume(0.6)
        try:
            self.payout_snd=pygame.mixer.Sound(self.asset_paths["payout"])
        except Exception:
            self.payout_snd=pygame.mixer.Sound(_wav(22050,0.12,_payout_snd))
        self.payout_snd.set_volume(0.62)
                                                                                                                                                            
        self.fan_snd=pygame.mixer.Sound(_wav(22050,0.5,_fan_snd)); self.fan_snd.set_volume(0.7)
                                                                                                                                                                          
        self.sw,self.sh=1400,960
                                                                                                                                                            
        self.screen=pygame.display.set_mode((self.sw,self.sh),pygame.RESIZABLE)
                                                                                                                                                            
        pygame.display.set_caption(f"Shelem \u2014 vs {AI_NAME}")
                                                                                                                                                            
        self.clock_tick=pygame.time.Clock()
                                                                                                                                                            
        self.R=Renderer(self.screen); self.R.update_scale(self.sw,self.sh)
        self.R.set_card_back_texture(self.asset_paths["card_back"])
                                                                                                                                                            
        self.game=ShelemGame(); self.ai=ShelemAI()
                                                                                                                                                            
        self.vmouse=(0,0); self.tick=0
                                                                                                                                                                          
        self.bid_value=MIN_BID
                                                                                                                                                                          
        self.card_rects_A=[]; self.pile_rects_A=[]; self.pile_rects_B=[]
                                                                                                                                                                          
        self.buttons={}
                                                                                                                                                                          
        self.time_minutes=10; self.match_target=1000
                                                                                                                                                                          
        self.ai_pending=False; self.ai_action_time=0
                                                                                                                                                                          
        self.show_history=False
                                                                                                                                                                          
        self.show_played=False
                                                                                                                                                                          
        self.show_analysis=True
                                                                                                                                                                          
        self.show_ai_hand=False
                                                                                                                                                            
        self.match_history=[]; self.load_history()
                                                                                                                                                                          
        self.fan_played=False
        self.payout_sound_ticks=deque()
        self.last_payout_sound_tick=-100000
        self.tactic_flash_text=""
        self.tactic_flash_until=0
        self.bg_music_mode=None
        self.bg_music_vol={"setup":0.44,"gameplay":0.42,"danger":0.5,"requiem":0.56}
        self.bg_music_track_index=0
        self.bg_music_track_count=1
        self.music_volume=1.0
        self.music_track_rect=None
        self.music_knob_rect=None
        self.music_dragging=False
        self.music_end_event=MUSIC_END_EVENT
        try:
            pygame.mixer.music.set_endevent(self.music_end_event)
        except Exception:
            self.music_end_event=None
        self.jaws_latched_round=None
                             
        self.save_store=SaveStateStore(SAVE_DB_FILE)
        self.timeline_store=GameTimelineStore(GAME_DB_FILE)
        self.tactic_store=TacticGradeStore(TACTICS_DB_FILE)
                                                                            
        self.timeline_game_id=None
        self.timeline_state_num=0
        self.timeline_last_fp=None
        self.timeline_last_fast_sig=None
        self.timeline_last_tick_ms=0
        self.timeline_nav_active=False
        self.timeline_nav_states=[]
        self.timeline_nav_index=0
        self.timeline_nav_live_index=0
        self.tactic_grade_open=False
        self.tactic_grade_target=None
        self.tactic_grade_buttons={}
                                       
        self.terminal_input=""
        self.terminal_active=False
        self.terminal_lines=deque(maxlen=2000)
        self.terminal_panel_rect=None
        self.terminal_input_rect=None
        self._terminal_cursor_t=0
        self.terminal_history=deque(maxlen=120)
        self.terminal_hist_index=None
        self.terminal_hist_draft=""
        self.terminal_scroll=0
        self.terminal_scroll_max=0
        self.terminal_row_rects=[]
        self._terminal_last_status=None
        self._terminal_announced_game_id=None
        self._terminal_last_round_summary=None
        self._terminal_last_match_summary=None
        self._jarvis_voice_next_tick=0
        self._jarvis_voice_last_key=None
        self._flavor_next_tick=0
        self._flavor_last_key=None
                                         
        self.db_inspector_open=False
        self.db_inspector_items=[]
        self.db_inspector_scroll=0
        self.db_close_rect=None
        self.db_row_rects=[]
                                                      
        self.replay_mode=replay_game_id is not None
        self.replay_game_id=_to_int(replay_game_id, 0) if replay_game_id is not None else None
        self.replay_states=[]
        self.replay_index=0
        if self.replay_mode:
            pygame.display.set_caption(f"Shelem Replay - Game #{self.replay_game_id}")
            self._init_replay_session(self.replay_game_id, replay_state_num)
        else:
            self._terminal_log("Terminal ready. /save /load [n] /load game [g] state [s] /inspect_db /history /played /tactics [n]")
        # Stu Ungar dead-hand judge state
        self.stu_ungar_active = False
        self.stu_ungar_playback = []   # list of (Card, player) to animate
        self.stu_ungar_played_so_far = []  # cards shown so far
        self.stu_ungar_last_card_ms = 0
        self.stu_ungar_card_interval_ms = 180  # ms between cards in animation
        self.stu_ungar_done_pause_ms = 1800    # ms to hold after all cards played
        self.stu_ungar_done_at_ms = 0
        self.stu_ungar_announced_round = -1
        self._stu_ungar_last_check_ms = 0
        self._stu_ungar_gif_frames = []
        self._stu_ungar_gif_frame_idx = 0
        self._stu_ungar_gif_last_ms = 0
        self._stu_ungar_gif_frame_ms = 80
        self._load_stu_ungar_gif()
        self._update_background_music(force=True)

                                                                                                                                                      
    def load_history(self):
                                                                                                                                                                          
        """Load persisted match history from JSON if available."""
                                                                                                                                                                    
        if os.path.exists(HISTORY_FILE):
                                                                                                                                           
            try:
                                                                                                                                                                 
                with open(HISTORY_FILE) as f: self.match_history=json.load(f)
                                                                                                                                                              
            except: pass
                                                                                                                                                      
    def save_history(self):
                                                                                                                                                            
        """Save recent match history to JSON (best effort)."""
                                                                                                                                       
        try:
                                                                                                                                                             
            with open(HISTORY_FILE,'w') as f: json.dump(self.match_history[-100:],f)
                                                                                                                                                          
        except: pass

    # ------------------------------------------------------------------
    # Stu Ungar dead-hand judge
    # ------------------------------------------------------------------

    def _load_stu_ungar_gif(self):
        """Load chiffre.gif animation frames using PIL if available, else static."""
        self._stu_ungar_gif_frames = []
        gif_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chiffre.gif")
        if not os.path.exists(gif_path):
            return
        try:
            from PIL import Image as _PILImage
            img = _PILImage.open(gif_path)
            try:
                while True:
                    frame = img.copy().convert("RGBA")
                    data = frame.tobytes()
                    pg_surf = pygame.image.fromstring(data, frame.size, "RGBA")
                    self._stu_ungar_gif_frames.append(pg_surf)
                    try:
                        dur = img.info.get("duration", 80)
                    except Exception:
                        dur = 80
                    self._stu_ungar_gif_frame_ms = max(40, int(dur))
                    img.seek(img.tell() + 1)
            except EOFError:
                pass
        except ImportError:
            try:
                surf = pygame.image.load(gif_path)
                self._stu_ungar_gif_frames = [surf]
            except Exception:
                pass
        except Exception:
            try:
                surf = pygame.image.load(gif_path)
                self._stu_ungar_gif_frames = [surf]
            except Exception:
                pass

    def _is_dead_hand(self, game):
        """Detect if remaining plays are determined regardless of card order.

        Returns (True, playback_sequence) if Stu Ungar should call the game,
        otherwise (False, None).

        Dead-hand conditions:
        1. All piles are empty (no hidden cards to flip)
        2. At least 3 tricks remain
        3. N random legal play-orderings all produce the same bid outcome
        """
        if game.state not in (State.PLAY_HAND_LEADER, State.PLAY_HAND_FOLLOWER):
            return False, None
        # All piles must be empty
        for p in range(2):
            for pile in game.piles[p]:
                if pile:
                    return False, None
        tricks_left = 12 - game.trick_num
        if game.trick_cards:
            tricks_left += 1
        if tricks_left < 3:
            return False, None
        # Sample N play orderings
        N_SAMPLES = 8
        outcomes = []
        first_seq = None
        for _ in range(N_SAMPLES):
            outcome, seq = self._simulate_hand_outcome(game)
            if outcome is None:
                return False, None
            outcomes.append(outcome)
            if first_seq is None and seq:
                first_seq = seq
        if len(outcomes) < N_SAMPLES:
            return False, None
        ref = outcomes[0]
        if all(o == ref for o in outcomes):
            return True, (first_seq or [])
        return False, None

    def _simulate_hand_outcome(self, game):
        """Play out remaining hand cards in random legal order.

        Returns (outcome_key: str, sequence: list[(Card, player)]) or (None, []).
        outcome_key encodes whether the bid was made/failed and final point totals.
        """
        try:
            g = copy.deepcopy(game)
            seq = []
            safety = 0
            # Advance any in-progress trick first
            while g.state == State.TRICK_RESULT:
                g.next_after_trick()
                safety += 1
                if safety > 20:
                    return None, []
            safety = 0
            while g.state in (State.PLAY_HAND_LEADER, State.PLAY_HAND_FOLLOWER):
                safety += 1
                if safety > 50:
                    return None, []
                player = g.active_player()
                if player is None:
                    break
                valid = g.get_valid_hand(player)
                if not valid:
                    break
                idx = random.choice(valid)
                card = g.hands[player][idx]
                seq.append((card.copy(), player))
                g.play_hand(player, idx)
                # Skip pile phase (piles are empty), so TRICK_RESULT comes next
                while g.state == State.TRICK_RESULT:
                    g.next_after_trick()
            if g.state == State.ROUND_END or g.trick_num >= 12:
                pts = [g.tricks_won[p] * 5 + card_points(g.cards_won[p]) for p in range(2)]
                w = g.bid_winner
                if w is not None:
                    made = pts[w] >= g.bid_amount
                    outcome = f"{'made' if made else 'failed'}_{pts[0]}_{pts[1]}"
                else:
                    outcome = f"no_bidder_{pts[0]}_{pts[1]}"
                return outcome, seq
            return None, []
        except Exception:
            return None, []

    def _trigger_stu_ungar(self, playback):
        """Announce and begin Stu Ungar dead-hand playback."""
        self.stu_ungar_active = True
        self.stu_ungar_playback = list(playback or [])
        self.stu_ungar_played_so_far = []
        self.stu_ungar_last_card_ms = self.tick + 600  # brief delay before first card
        self.stu_ungar_done_at_ms = 0
        self.stu_ungar_announced_round = self.game.round_num
        G = self.game
        tricks_left = 12 - G.trick_num
        bid_name = f"${G.bid_amount}" if G.bid_amount else "?"
        bidder_name = player_name(G.bid_winner) if G.bid_winner is not None else "?"
        self._terminal_log(
            f"[STU UNGAR] I'm calling this game! {tricks_left} tricks remain — "
            f"outcome is DETERMINED. Bid {bid_name} by {bidder_name}.",
            color=(220, 180, 0), suit_colors=False
        )
        self._terminal_log(
            "[STU UNGAR] Playing out the remaining cards...",
            color=(220, 180, 0), suit_colors=False
        )

    def _tick_stu_ungar(self):
        """Advance Stu Ungar animation each frame when active."""
        if not self.stu_ungar_active:
            return
        t = self.tick
        # Done showing all cards — wait, then resolve
        if self.stu_ungar_done_at_ms > 0:
            if t >= self.stu_ungar_done_at_ms:
                self._resolve_stu_ungar()
            return
        # Time to show next card?
        if t < self.stu_ungar_last_card_ms:
            return
        idx = len(self.stu_ungar_played_so_far)
        if idx >= len(self.stu_ungar_playback):
            # All cards shown — start done timer
            self.stu_ungar_done_at_ms = t + self.stu_ungar_done_pause_ms
            return
        card, player = self.stu_ungar_playback[idx]
        self.stu_ungar_played_so_far.append((card, player))
        self.stu_ungar_last_card_ms = t + self.stu_ungar_card_interval_ms
        self.card_snd.play()

    def _resolve_stu_ungar(self):
        """Finish Stu Ungar playback — play out the actual game state and score."""
        self.stu_ungar_active = False
        G = self.game
        try:
            safety = 0
            # Play all remaining hand cards in the playback order
            played_cards = [(c.rank, c.suit, p) for c, p in self.stu_ungar_playback]
            for rank, suit, player in played_cards:
                safety += 1
                if safety > 60:
                    break
                if G.state not in (State.PLAY_HAND_LEADER, State.PLAY_HAND_FOLLOWER):
                    if G.state == State.TRICK_RESULT:
                        G.next_after_trick()
                    if G.state not in (State.PLAY_HAND_LEADER, State.PLAY_HAND_FOLLOWER):
                        break
                ap = G.active_player()
                if ap != player:
                    break
                valid = G.get_valid_hand(ap)
                if not valid:
                    break
                # Find the matching card index
                ci = None
                for vi in valid:
                    if vi < len(G.hands[ap]) and G.hands[ap][vi].rank == rank and G.hands[ap][vi].suit == suit:
                        ci = vi
                        break
                if ci is None:
                    ci = valid[0]
                card = G.play_hand(ap, ci)
                self.ai.tracker.card_played(card, ap)
                if G.state == State.TRICK_RESULT:
                    self.ai.tracker.trick_done()
                    G.next_after_trick()
            # If still not at ROUND_END, force remaining tricks
            while G.state in (State.PLAY_HAND_LEADER, State.PLAY_HAND_FOLLOWER, State.TRICK_RESULT):
                safety += 1
                if safety > 100:
                    break
                if G.state == State.TRICK_RESULT:
                    self.ai.tracker.trick_done()
                    G.next_after_trick()
                elif G.state in (State.PLAY_HAND_LEADER, State.PLAY_HAND_FOLLOWER):
                    ap = G.active_player()
                    if ap is None:
                        break
                    valid = G.get_valid_hand(ap)
                    if not valid:
                        break
                    card = G.play_hand(ap, valid[0])
                    self.ai.tracker.card_played(card, ap)
        except Exception:
            pass
        # Force round end if not already there
        if G.state not in (State.ROUND_END, State.SHELEM_CELEBRATION, State.MATCH_OVER):
            try:
                G._end_round()
            except Exception:
                pass
        if G.state == State.ROUND_END:
            self._queue_payout_sounds(G.score_deltas)
            G.auto_timer = self.tick + 800

    def _draw_stu_ungar_popup(self):
        """Render the Stu Ungar dead-hand popup with chiffre.gif and card animation.

        The popup shows:
          • chiffre.gif animated at the top
          • Cards played so far in the auto-playback sequence
          • A progress bar showing how many cards remain
        """
        R = self.R
        cx, cy = VW / 2, VH / 2
        pw, ph = 1050, 720

        # ------ background panel ------
        sr = R.r(cx - pw / 2, cy - ph / 2, pw, ph)
        bg = pygame.Surface((sr.w, sr.h), pygame.SRCALPHA)
        bg.fill((8, 8, 28, 235))
        self.screen.blit(bg, sr.topleft)
        pygame.draw.rect(self.screen, (220, 180, 0), sr, max(2, R.s(3)),
                         border_radius=max(4, R.s(14)))

        # ------ animated chiffre.gif at the top ------
        gif_target_h = max(20, int(R.s(88)))
        gif_drawn = False
        if self._stu_ungar_gif_frames:
            t = self.tick
            if t - self._stu_ungar_gif_last_ms >= self._stu_ungar_gif_frame_ms:
                self._stu_ungar_gif_frame_idx = (
                    (self._stu_ungar_gif_frame_idx + 1) % len(self._stu_ungar_gif_frames)
                )
                self._stu_ungar_gif_last_ms = t
            frame = self._stu_ungar_gif_frames[self._stu_ungar_gif_frame_idx]
            fh = max(1, frame.get_height())
            fw = max(1, frame.get_width())
            scale_f = gif_target_h / fh
            tw = max(1, int(fw * scale_f))
            try:
                scaled = pygame.transform.smoothscale(frame, (tw, gif_target_h))
                fx = self.screen.get_width() // 2 - tw // 2
                fy = sr.top + max(4, R.s(6))
                self.screen.blit(scaled, (fx, fy))
                gif_drawn = True
            except Exception:
                pass

        # ------ title text ------
        title_vy = cy - ph / 2 + (90 if gif_drawn else 14)
        R.draw_text_center("✦ STU UNGAR CALLS THE GAME ✦", title_vy, "bold", 25, (220, 180, 0))
        R.draw_text_center("Outcome is determined — playing out remaining cards",
                           title_vy + 34, "ui_sm", 17, (190, 190, 190))

        # ------ card animation area ------
        # Cards drawn at 48% of normal size in virtual coordinates
        card_scale = 0.48
        vcw = BASE_CW * card_scale
        vch = BASE_CH * card_scale
        gap_x = vcw + 12
        gap_y = vch + 22
        area_left = cx - pw / 2 + 28
        area_top = title_vy + 62
        max_per_row = max(1, int((pw - 56) // gap_x))
        trump = self.game.trump_suit

        cards_shown = list(self.stu_ungar_played_so_far)
        for ci, (card, player) in enumerate(cards_shown):
            col = ci % max_per_row
            row_i = ci // max_per_row
            vx = area_left + col * gap_x
            vy = area_top + row_i * gap_y
            # Draw mini card using scaled virtual coords via the renderer's rect helper
            scr_rect = R.r(vx, vy, vcw, vch)
            rad = max(2, R.s(6))
            # Background
            bg_col = (245, 245, 245) if card.suit in ('♥', '♦') else (245, 245, 245)
            trump_glow = card.suit == trump
            border_col = (255, 210, 50) if trump_glow else (160, 160, 160)
            pygame.draw.rect(self.screen, bg_col, scr_rect, border_radius=rad)
            pygame.draw.rect(self.screen, border_col, scr_rect, max(1, R.s(2)),
                             border_radius=rad)
            # Rank + suit text
            suit_colors = {'♠': (20, 20, 20), '♣': (20, 20, 20),
                           '♥': (200, 30, 30), '♦': (200, 30, 30)}
            sc = suit_colors.get(card.suit, (20, 20, 20))
            fsize = max(8, int(R.s(12)))
            lbl_surf = R.font("bold", fsize).render(f"{card.rank}{card.suit}", True, sc)
            self.screen.blit(lbl_surf, lbl_surf.get_rect(
                centerx=scr_rect.centerx, centery=scr_rect.centery))
            # Player label below card
            who_col = (120, 220, 120) if player == HUMAN else (120, 160, 255)
            pfsize = max(7, int(R.s(9)))
            plbl = R.font("ui_sm", pfsize).render(player_name(player)[:1], True, who_col)
            self.screen.blit(plbl, plbl.get_rect(
                centerx=scr_rect.centerx, top=scr_rect.bottom + max(1, R.s(2))))

        # ------ progress bar ------
        total_cards = len(self.stu_ungar_playback)
        if total_cards > 0:
            bar_vy = cy + ph / 2 - 52
            bar_vw = pw - 80
            bar_vh = 14
            bar_sr = R.r(cx - bar_vw / 2, bar_vy, bar_vw, bar_vh)
            pygame.draw.rect(self.screen, (40, 40, 65), bar_sr,
                             border_radius=max(2, R.s(7)))
            done_frac = min(1.0, len(cards_shown) / total_cards)
            if done_frac > 0:
                fill_sr = pygame.Rect(bar_sr.x, bar_sr.y,
                                      max(1, int(bar_sr.w * done_frac)), bar_sr.h)
                pygame.draw.rect(self.screen, (220, 180, 0), fill_sr,
                                 border_radius=max(2, R.s(7)))
            prog_txt = R.font("ui_sm", max(12, int(R.s(15)))).render(
                f"{len(cards_shown)} / {total_cards} cards played", True, (180, 180, 180))
            self.screen.blit(prog_txt, prog_txt.get_rect(
                centerx=self.screen.get_width() // 2,
                top=bar_sr.bottom + max(2, R.s(4))))

    def _log_round_analysis(self):
        """Post-round terminal analysis: highlight Jarvis's key mistakes and good plays."""
        G = self.game
        tricks = self.ai.tracker.trick_history
        if not tricks:
            return
        trump = G.trump_suit
        bid_w = G.bid_winner
        bid_amt = G.bid_amount
        ai_pts = G.round_points[AI_PLAYER] if hasattr(G, 'round_points') else 0
        hu_pts = G.round_points[HUMAN] if hasattr(G, 'round_points') else 0
        ai_delta = G.score_deltas[AI_PLAYER] if hasattr(G, 'score_deltas') else 0

        issues = []
        good_plays = []

        jarvis_points_dumped = 0    # pts Jarvis gave away on losing tricks
        jarvis_missed_ruffs = 0     # times Jarvis could have ruffed but didn't
        human_free_pts = 0          # pts human scored uncontested

        for trick in tricks:
            if len(trick) < 2:
                continue
            led_suit = trick[0][0].suit
            pot = sum(c.points() for c, _ in trick)
            # Determine winner
            best_pw = -1
            tw = None
            for c, p in trick:
                pw = c.trick_power(led_suit, trump)
                if pw > best_pw:
                    best_pw = pw; tw = p
            # Check if Jarvis dumped points on a losing trick
            for c, p in trick:
                if p == AI_PLAYER and tw != AI_PLAYER and c.points() > 0:
                    jarvis_points_dumped += c.points()
                    issues.append(f"Trick {tricks.index(trick)+1}: Jarvis dumped {c.points()}pts ({c}) on losing trick")
            # Check if human scored unopposed value
            if tw == HUMAN and pot >= 10:
                human_free_pts += pot
            # Check missed ruff: Jarvis void in led suit but didn't play trump
            ai_plays = [(c, p) for c, p in trick if p == AI_PLAYER]
            if ai_plays and led_suit != trump:
                ai_card, _ = ai_plays[0]
                ai_is_void = ai_card.suit != led_suit
                ai_ruffed = ai_card.suit == trump
                if ai_is_void and not ai_ruffed:
                    jarvis_missed_ruffs += 1
                    issues.append(f"Trick {tricks.index(trick)+1}: Jarvis void in {led_suit} but did NOT ruff (played {ai_card})")

        # Contract analysis
        if bid_w == AI_PLAYER:
            if ai_delta < 0:
                issues.insert(0, f"CONTRACT FAILED: Jarvis bid ${bid_amt} but scored only ${ai_pts} — penalty ${-ai_delta}")
            elif ai_pts < bid_amt + 20:
                issues.insert(0, f"Contract tight: Jarvis bid ${bid_amt}, scored ${ai_pts} (margin: ${ai_pts-bid_amt})")
        elif bid_w == HUMAN:
            if ai_delta > 0 and hu_pts < bid_amt:
                good_plays.append(f"Defense: Jarvis limited human to ${hu_pts} vs bid ${bid_amt}")

        if jarvis_points_dumped > 0:
            issues.append(f"Total: Jarvis leaked {jarvis_points_dumped}pts on losing tricks")
        if human_free_pts >= 20:
            issues.append(f"Human scored {human_free_pts}pts essentially unopposed")
        if jarvis_missed_ruffs > 0:
            issues.append(f"Jarvis missed {jarvis_missed_ruffs} ruff opportunity(ies)")

        if issues:
            self._terminal_log(f"[ANALYSIS R{G.round_num}] JARVIS CRITIQUE:", color=(255, 120, 60), suit_colors=False)
            for iss in issues[:5]:
                self._terminal_log(f"  ✗ {iss}", color=(220, 100, 60), suit_colors=False)
        if good_plays:
            self._terminal_log(f"[ANALYSIS R{G.round_num}] JARVIS GOOD:", color=(80, 200, 100), suit_colors=False)
            for gp in good_plays[:2]:
                self._terminal_log(f"  ✓ {gp}", color=(80, 200, 100), suit_colors=False)

    def _terminal_log(self, text, color=None, suit_colors=True):
        """Append one line to the in-game terminal output."""
        if color is None:
            color=(28,28,28)
        entry={
            "text": str(text),
            "color": [int(max(0, min(255, _to_int(color[0], 28)))),
                      int(max(0, min(255, _to_int(color[1], 28)))),
                      int(max(0, min(255, _to_int(color[2], 28))))],
            "suit_colors": bool(suit_colors),
        }
        self.terminal_lines.append(entry)
        if self.terminal_scroll>0:
            self.terminal_scroll+=1

    def _terminal_entry(self, raw):
        """Normalize terminal line payload (legacy string or styled dict)."""
        if isinstance(raw, dict):
            txt=str(raw.get("text", ""))
            col=raw.get("color", [28,28,28])
            if isinstance(col, (list, tuple)) and len(col)>=3:
                color=(
                    int(max(0, min(255, _to_int(col[0], 28)))),
                    int(max(0, min(255, _to_int(col[1], 28)))),
                    int(max(0, min(255, _to_int(col[2], 28)))),
                )
            else:
                color=(28,28,28)
            return {"text": txt, "color": color, "suit_colors": bool(raw.get("suit_colors", True))}
        return {"text": str(raw), "color": (28,28,28), "suit_colors": True}

    def _terminal_log_jarvis(self, options, *, key=None, weight=1.0, force=False):
        """Occasionally write Jarvis personality lines in red."""
        if self.replay_mode:
            return
        raw_opts=list(options or [])
        opt_n=min(24, max(6, len(raw_opts)//2)) if raw_opts else 0
        msgs=_pick_quote_pool(raw_opts, opt_n) if opt_n>0 else []
        if JARVIS_PHRASEBOOK:
            extra_n=min(12, max(6, len(JARVIS_PHRASEBOOK)//18))
            msgs.extend(_pick_quote_pool(JARVIS_PHRASEBOOK, extra_n))
        if not msgs:
            return
        now=max(0, _to_int(self.tick, 0))
        if not force:
            if now<self._jarvis_voice_next_tick:
                return
            if key is not None and key==self._jarvis_voice_last_key:
                return
            p=max(0.10, min(0.88, 0.22*float(weight)))
            if random.random()>p:
                return
        msg=random.choice(msgs)
        self._terminal_log(f"[{self._state_code(self.game)}] JARVIS: {msg}", color=(180,32,32), suit_colors=False)
        self._jarvis_voice_last_key=key
        self._jarvis_voice_next_tick=now+random.randint(2400, 5600)

    def _sync_game_status_to_terminal(self):
        """Emit sparse timeline updates (game start, round summary, match summary)."""
        G=self.game
        gid=self._current_game_id()
        key=(
            gid,
            G.state,
            int(getattr(G, "round_num", 0)),
            int(getattr(G, "trick_num", 0)),
            int(getattr(G, "scores", [0,0])[0] if hasattr(G, "scores") else 0),
            int(getattr(G, "scores", [0,0])[1] if hasattr(G, "scores") else 0),
            int(getattr(G, "bid_amount", 0)),
            str(getattr(G, "bonus_msg", "") or ""),
        )
        if key==self._terminal_last_status:
            return
        self._terminal_last_status=key
        changed=False
        if G.state!=State.MATCH_START and gid is not None and gid!=self._terminal_announced_game_id:
            self._terminal_log(f"[{self._state_code(G)}] Game begins.")
            self._terminal_announced_game_id=gid
            changed=True
        if G.state==State.ROUND_END:
            rkey=(
                gid,
                int(getattr(G, "round_num", 0)),
                int(getattr(G, "round_points", [0,0])[0] if hasattr(G, "round_points") else 0),
                int(getattr(G, "round_points", [0,0])[1] if hasattr(G, "round_points") else 0),
                int(getattr(G, "score_deltas", [0,0])[0] if hasattr(G, "score_deltas") else 0),
                int(getattr(G, "score_deltas", [0,0])[1] if hasattr(G, "score_deltas") else 0),
                int(getattr(G, "scores", [0,0])[0] if hasattr(G, "scores") else 0),
                int(getattr(G, "scores", [0,0])[1] if hasattr(G, "scores") else 0),
                int(getattr(G, "bid_amount", 0)),
                int(getattr(G, "bid_winner", -1)) if getattr(G, "bid_winner", None) is not None else -1,
            )
            if rkey!=self._terminal_last_round_summary:
                self._terminal_round_summary()
                self._terminal_last_round_summary=rkey
                changed=True
        if G.state==State.MATCH_OVER:
            mkey=(
                gid,
                int(getattr(G, "round_num", 0)),
                int(getattr(G, "scores", [0,0])[0] if hasattr(G, "scores") else 0),
                int(getattr(G, "scores", [0,0])[1] if hasattr(G, "scores") else 0),
                int(getattr(G, "match_winner", -1)) if getattr(G, "match_winner", None) is not None else -1,
            )
            if mkey!=self._terminal_last_match_summary:
                self._terminal_match_summary()
                self._terminal_last_match_summary=mkey
                changed=True
        if changed and not self.replay_mode and self.timeline_game_id is not None:
            self._record_timeline_state("terminal", force=True)

    def _terminal_round_summary(self):
        """Round-end compact summary for terminal output."""
        G=self.game
        code=self._state_code(G)
        rp=(getattr(G, "round_points", [0,0]) or [0,0])
        sd=(getattr(G, "score_deltas", [0,0]) or [0,0])
        rp0=_to_int(rp[0] if len(rp)>0 else 0, 0)
        rp1=_to_int(rp[1] if len(rp)>1 else 0, 0)
        sd0=_to_int(sd[0] if len(sd)>0 else 0, 0)
        sd1=_to_int(sd[1] if len(sd)>1 else 0, 0)
        bidder=player_name(G.bid_winner) if G.bid_winner in (HUMAN, AI_PLAYER) else "?"
        bid_amt=_to_int(getattr(G, "bid_amount", 0), 0)
        line=(
            f"[{code}] Round {G.round_num} summary: bid {bidder} ${bid_amt} | "
            f"{HUMAN_NAME} {rp0:+d} pts ({sd0:+d}$), "
            f"{AI_NAME} {rp1:+d} pts ({sd1:+d}$)"
        )
        self._terminal_log(line)
        self._terminal_log(
            f"[{code}] Match score: {HUMAN_NAME} {money_text(G.scores[HUMAN])} | {AI_NAME} {money_text(G.scores[AI_PLAYER])}"
        )
        bidder_pts=rp0 if G.bid_winner==HUMAN else rp1 if G.bid_winner==AI_PLAYER else 0
        if bidder_pts>=TOTAL_PTS and bid_amt>=MAX_BID:
            self._terminal_log(f"[{code}] Super Shelem / shelem baste: full contract, full capture.")
        elif bidder_pts>=TOTAL_PTS:
            self._terminal_log(f"[{code}] Shelem: all tricks secured this round.")
        if getattr(G, "bonus_msg", ""):
            self._terminal_log(f"[{code}] {G.bonus_msg}")
        gid=self._current_game_id()
        diff=sd1-sd0
        if diff>=35 or rp1>=95:
            self._terminal_log_jarvis(
                JARVIS_QUOTES_ROUND_AI_UP,
                key=("jarvis_round_up", gid, G.round_num, diff, rp1),
                weight=0.90,
            )
        elif diff<=-25 or (G.bid_winner==AI_PLAYER and rp1<bid_amt):
            self._terminal_log_jarvis(
                JARVIS_QUOTES_ROUND_AI_DOWN,
                key=("jarvis_round_down", gid, G.round_num, diff, rp1, bid_amt),
                weight=0.85,
            )

    def _terminal_match_summary(self):
        """Match-end compact summary for terminal output."""
        G=self.game
        code=self._state_code(G)
        winner=player_name(G.match_winner) if G.match_winner in (HUMAN, AI_PLAYER) else "No winner"
        self._terminal_log(
            f"[{code}] Match summary: {winner} after {int(getattr(G, 'round_num', 0))} rounds."
        )
        self._terminal_log(
            f"[{code}] Final: {HUMAN_NAME} {money_text(G.scores[HUMAN])} | {AI_NAME} {money_text(G.scores[AI_PLAYER])}"
        )
        gid=self._current_game_id()
        if G.match_winner==AI_PLAYER:
            self._terminal_log_jarvis(
                JARVIS_QUOTES_MATCH_AI_WIN,
                key=("jarvis_match_win", gid, G.round_num),
                weight=1.0,
                force=True,
            )
        elif G.match_winner==HUMAN:
            self._terminal_log_jarvis(
                JARVIS_QUOTES_MATCH_AI_LOSS,
                key=("jarvis_match_loss", gid, G.round_num),
                weight=1.0,
                force=True,
            )

    def _remember_terminal_command(self, cmd):
        """Store command in history for up/down recall."""
        c=(cmd or "").strip()
        if not c:
            return
        if not self.terminal_history or self.terminal_history[-1]!=c:
            self.terminal_history.append(c)
        self.terminal_hist_index=None
        self.terminal_hist_draft=""

    def _current_game_id(self):
        """Return timeline game id (or replay game id in replay window)."""
        if self.replay_mode and self.replay_game_id is not None:
            return _to_int(self.replay_game_id, 0)
        if self.timeline_game_id is not None:
            return _to_int(self.timeline_game_id, 0)
        return None

    def _state_bucket_phase(self, game=None):
        """Map current FSM state into compact numeric (trick-bucket, phase) code."""
        g=game if game is not None else self.game
        st=g.state
        trick=_to_int(getattr(g, "trick_num", 0), 0)
        play_phase={
            State.PLAY_HAND_LEADER: 1,
            State.PLAY_HAND_FOLLOWER: 2,
            State.PLAY_PILE_LEADER: 3,
            State.PLAY_PILE_FOLLOWER: 4,
            State.TRICK_RESULT: 5,
        }
        if st in play_phase:
            return max(1, trick), play_phase[st]
        pre_phase={
            State.MATCH_START: (-3, 0),
            State.BIDDING: (-2, 0),
            State.TAKE_SPECIAL: (-2, 1),
            State.DISCARDING: (-2, 2),
            State.TRUMP_SELECT: (-2, 3),
            State.ROUND_END: (-1, 0),
            State.SHELEM_CELEBRATION: (-1, 1),
            State.MATCH_OVER: (0, 0),
        }
        return pre_phase.get(st, (0, 0))

    def _state_code(self, game=None):
        """Return numeric state code in format game.trickOrPhase.phaseIndex."""
        gid=self._current_game_id()
        tb,ph=self._state_bucket_phase(game)
        gtxt=str(gid) if gid is not None else "?"
        return f"{gtxt}.{tb}.{ph}"

    def _log_played_cards(self):
        """Emit played cards grouped by suit into terminal."""
        G=self.game
        code=self._state_code(G)
        rows=self.ai.tracker.played_by_suit()
        total=sum(len(rows.get(s, [])) for s in SUITS)
        self._terminal_log(f"[{code}] Played cards by suit ({total}/52):")
        for s in SUITS:
            cards=rows.get(s, [])
            items=" ".join(card_ui_text(c) for c in sorted(cards, key=lambda c: RANK_ORDER[c.rank]))
            self._terminal_log(f"{s}: {items if items else '-'}")

    def _persian_suit_name(self, suit):
        return PERSIAN_SUIT_NAMES.get(suit, SUIT_NAMES.get(suit, str(suit)))

    def _persian_rank_name(self, rank):
        return PERSIAN_RANK_NAMES.get(str(rank), str(rank))

    def _persian_card_name(self, card):
        if card is None:
            return "?"
        return f"{self._persian_rank_name(card.rank)}-e {self._persian_suit_name(card.suit)}"

    def _log_farsi_flavor(self, options, *, key=None, weight=1.0, force=False):
        """Occasionally inject transliterated Iranian Shelem/Hokm flavor text."""
        if self.replay_mode:
            return
        msgs=[str(x).strip() for x in (options or []) if str(x).strip()]
        if not msgs:
            return
        now=max(0, _to_int(self.tick, 0))
        if not force:
            if now<self._flavor_next_tick:
                return
            if key is not None and key==self._flavor_last_key:
                return
            p=max(0.06, min(0.80, 0.20*float(weight)))
            if random.random()>p:
                return
        msg=random.choice(msgs)
        self._terminal_log(f"[{self._state_code(self.game)}] {msg}")
        self._flavor_last_key=key
        self._flavor_next_tick=now+random.randint(1200, 3400)

    def _emit_bid_flavor(self, player, amount=None, passed=False):
        """Flavor for bidding ('elan', hakem pressure, shelem calls)."""
        if passed:
            msgs=[
                f"Rad dadan by {player_name(player)}. No elan, just patience.",
                f"{player_name(player)} says rad dadan and folds this bid duel.",
            ]
            self._log_farsi_flavor(msgs, key=("bid_pass", self._current_game_id(), self.game.round_num, player), weight=0.34)
            if player==AI_PLAYER:
                self._terminal_log_jarvis(
                    JARVIS_QUOTES_AI_BAD,
                    key=("jarvis_bid_pass_ai", self._current_game_id(), self.game.round_num, player),
                    weight=0.24,
                )
            return
        amt=_to_int(amount, 0)
        if amt>=MAX_BID:
            msgs=[
                f"Shelem elan at ${amt}! Hakem energy just went all-in.",
                f"Bold elan: ${amt}. If this lands, that's pure shelem swagger.",
            ]
            self._log_farsi_flavor(msgs, key=("bid_shelem", self._current_game_id(), self.game.round_num, player), weight=0.62)
            self._terminal_log_jarvis(
                JARVIS_QUOTES_BID_PRESSURE_HUMAN if player==HUMAN else JARVIS_QUOTES_BID_PRESSURE_AI,
                key=("jarvis_bid_shelem", self._current_game_id(), self.game.round_num, player, amt),
                weight=0.70,
            )
            return
        msgs=[
            f"Elan: {player_name(player)} pushes the bid to ${amt}.",
            f"{player_name(player)} calls elan/khundan at ${amt}; hakem race is on.",
        ]
        self._log_farsi_flavor(msgs, key=("bid", self._current_game_id(), self.game.round_num, player, amt), weight=0.42)
        if amt>=110:
            self._terminal_log_jarvis(
                JARVIS_QUOTES_BID_PRESSURE_HUMAN if player==HUMAN else JARVIS_QUOTES_BID_PRESSURE_AI,
                key=("jarvis_bid_pressure", self._current_game_id(), self.game.round_num, player, amt),
                weight=0.52,
            )

    def _emit_trump_flavor(self, player, suit):
        """Flavor for trump selection ('hokm')."""
        sname=self._persian_suit_name(suit)
        msgs=[
            f"Hokm set: {sname}. {player_name(player)} is now the hakem/hokmbar.",
            f"{player_name(player)} calls hokm on {sname}. Watch the boridan traps.",
        ]
        self._log_farsi_flavor(msgs, key=("hokm", self._current_game_id(), self.game.round_num, suit), force=True)

    def _emit_discard_flavor(self, player, discarded):
        """Flavor for discard phase ('riz kardan')."""
        cards=[c for c in (discarded or []) if c is not None]
        if not cards:
            return
        pts=sum(c.points() for c in cards)
        msgs=[
            f"Riz kardan by {player_name(player)}. Four cards gone, table pressure up.",
            f"{player_name(player)} does riz kardan before hokm play.",
        ]
        if pts>0:
            msgs.append(f"Riz kardan with {pts} points tossed. Cold blood.")
        self._log_farsi_flavor(msgs, key=("discard", self._current_game_id(), self.game.round_num, player), weight=0.55)

    def _emit_card_play_flavor(self, player, card, led_suit, trump_suit):
        """Flavor for play events: chagh/boridan/riz/rad/sar-e hokm."""
        if card is None:
            return
        gid=self._current_game_id()
        round_num=_to_int(getattr(self.game, "round_num", 0), 0)
        trick_num=_to_int(getattr(self.game, "trick_num", 0), 0)
        card_name=self._persian_card_name(card)
        if card.points()>0:
            msgs=[
                f"Chagh kardan: {player_name(player)} throws {card_name}. Points on the zamin now.",
                f"Chagh kardan by {player_name(player)} with {card_name}. Nice greed, now defend it.",
            ]
            if str(card.rank)=="5":
                msgs.append(f"Pa tol alert: {card_name} enters the fight. Somebody will cry over this trick.")
            self._log_farsi_flavor(msgs, key=("chagh", gid, round_num, trick_num, player, card.id52()), weight=0.72)
            bad_point_dump=bool(led_suit and card.suit!=led_suit and not (trump_suit and card.suit==trump_suit))
            if player==AI_PLAYER:
                self._terminal_log_jarvis(
                    JARVIS_QUOTES_POINT_AI,
                    key=("jarvis_point_play_ai", gid, round_num, trick_num, card.id52()),
                    weight=0.56,
                )
            elif player==HUMAN:
                self._terminal_log_jarvis(
                    JARVIS_QUOTES_HUMAN_BAD if bad_point_dump else JARVIS_QUOTES_POINT_HUMAN,
                    key=("jarvis_point_play_human", gid, round_num, trick_num, card.id52(), bad_point_dump),
                    weight=0.62 if bad_point_dump else 0.58,
                )
            return
        if led_suit is None and trump_suit and card.suit==trump_suit:
            msgs=[
                f"Sar-e hokm from {player_name(player)} with {card_name}. No hiding now.",
                f"{player_name(player)} opens sar-e hokm. Straight pressure play.",
            ]
            self._log_farsi_flavor(msgs, key=("sar_hokm", gid, round_num, trick_num, player), weight=0.64)
            self._terminal_log_jarvis(
                JARVIS_QUOTES_TRUMP_LEAD_AI if player==AI_PLAYER else JARVIS_QUOTES_TRUMP_LEAD_HUMAN,
                key=("jarvis_trump_lead", gid, round_num, trick_num, player, card.id52()),
                weight=0.56,
            )
            return
        if led_suit and card.suit!=led_suit:
            if trump_suit and card.suit==trump_suit:
                msgs=[
                    f"Boridan! {player_name(player)} cuts with {card_name}. Trick stolen mid-air.",
                    f"Boridan by {player_name(player)}. Hokm bites hard on this zamin.",
                ]
                self._log_farsi_flavor(msgs, key=("boridan", gid, round_num, trick_num, player, card.id52()), weight=0.62)
                self._terminal_log_jarvis(
                    JARVIS_QUOTES_CUT_AI if player==AI_PLAYER else JARVIS_QUOTES_CUT_HUMAN,
                    key=("jarvis_cut", gid, round_num, trick_num, player, card.id52()),
                    weight=0.62,
                )
                return
            msgs=[
                f"Riz kardan / rad dadan by {player_name(player)} with {card_name}. No follow-suit available.",
                f"{player_name(player)} goes rad dadan and dumps {card_name}. Tactical retreat.",
            ]
            self._log_farsi_flavor(msgs, key=("riz_rad", gid, round_num, trick_num, player, card.id52()), weight=0.46)
            self._terminal_log_jarvis(
                JARVIS_QUOTES_DUMP_AI if player==AI_PLAYER else JARVIS_QUOTES_DUMP_HUMAN,
                key=("jarvis_dump", gid, round_num, trick_num, player, card.id52()),
                weight=0.44,
            )

    def _log_round_history(self):
        """Emit compact game history (bidding + trick-by-trick) into terminal."""
        G=self.game
        code=self._state_code(G)
        self._terminal_log(f"[{code}] Game history snapshot")
        self._terminal_log(f"Round {G.round_num} | State {G.state.name} | Trick {max(0,_to_int(G.trick_num,0))}/12")
        self._terminal_log(
            f"Match score: {HUMAN_NAME} {money_text(G.scores[HUMAN])} | {AI_NAME} {money_text(G.scores[AI_PLAYER])}"
        )
        if G.bid_winner is not None:
            self._terminal_log(f"Contract: {player_name(G.bid_winner)} @ ${_to_int(G.bid_amount,0)}")
        else:
            self._terminal_log("Contract: not decided")
        if G.trump_suit:
            self._terminal_log(f"Trump: {G.trump_suit}")
        bids=(getattr(G, "last_bid", [0,0]) or [0,0])
        bp=(getattr(G, "bid_passed", [False,False]) or [False,False])
        self._terminal_log(
            f"Bids: {HUMAN_NAME}=${_to_int(bids[0],0)}{' pass' if bool(bp[0]) else ''} | "
            f"{AI_NAME}=${_to_int(bids[1] if len(bids)>1 else 0,0)}{' pass' if bool(bp[1] if len(bp)>1 else False) else ''}"
        )
        gid=self._current_game_id()
        states=[]
        if self.replay_mode:
            states=list(self.replay_states)
        elif gid is not None:
            try:
                states=self.timeline_store.load_game_states(gid)
            except Exception:
                states=[]
        timeline_rows=[]
        seen=set()
        for sn,snap in states:
            game_data=(snap or {}).get("game") or {}
            st_name=str(game_data.get("state", ""))
            rnum=_to_int(game_data.get("round_num", 0), 0)
            tnum=_to_int(game_data.get("trick_num", 0), 0)
            if st_name!="TRICK_RESULT" or rnum<=0 or tnum<=0:
                continue
            key=(rnum, tnum)
            if key in seen:
                continue
            tr=_trick_from_data(game_data.get("trick_cards", []))
            if len(tr)!=2:
                continue
            seen.add(key)
            timeline_rows.append((rnum, tnum, tr, game_data.get("trump_suit", None), _to_int(sn, 0)))
        timeline_rows.sort(key=lambda x: (x[0], x[1], x[4]))
        if timeline_rows:
            for rnum,tnum,tr,trump,_sn in timeline_rows:
                led=tr[0][0].suit
                try:
                    winner=max(tr, key=lambda cp: cp[0].trick_power(led, trump))[1]
                except Exception:
                    winner=tr[0][1]
                seq=" | ".join(f"{player_name(p)}:{card_ui_text(c)}" for c,p in tr)
                pts=5+sum(c.points() for c,_ in tr)
                code_t=f"{gid if gid is not None else '?'}.{tnum}.5"
                self._terminal_log(f"[{code_t}] R{rnum:02d} T{tnum:02d} {seq} -> {player_name(winner)} (+{pts})")
        else:
            hist=self.ai.tracker.all_tricks()
            if not hist and not G.trick_cards:
                self._terminal_log("No trick events yet.")
                return
            tnum=0
            for tr in hist:
                if not tr:
                    continue
                if len(tr)!=2:
                    owner=player_name(tr[0][1]) if tr and len(tr[0])>1 else "?"
                    cards=" ".join(card_ui_text(c) for c,_ in tr)
                    self._terminal_log(f"Special/discard ({owner}): {cards}")
                    continue
                tnum+=1
                led=tr[0][0].suit
                try:
                    winner=max(tr, key=lambda cp: cp[0].trick_power(led, G.trump_suit))[1]
                except Exception:
                    winner=tr[0][1]
                seq=" | ".join(f"{player_name(p)}:{card_ui_text(c)}" for c,p in tr)
                pts=5+sum(c.points() for c,_ in tr)
                code_t=f"{gid if gid is not None else '?'}.{tnum}.5"
                self._terminal_log(f"[{code_t}] T{tnum:02d} {seq} -> {player_name(winner)} (+{pts})")
        if G.trick_cards:
            seq=" | ".join(f"{player_name(p)}:{card_ui_text(c)}" for c,p in G.trick_cards)
            self._terminal_log(f"[{self._state_code(G)}] Current trick: {seq}")

    def _ensure_game_runtime_defaults(self, game):
        """Ensure game object has all transient fields expected by draw/logic code."""
        if not hasattr(game, "hands"): game.hands=[[],[]]
        if not hasattr(game, "special_pile"): game.special_pile=[]
        if not hasattr(game, "piles"): game.piles=[[],[]]
        if not hasattr(game, "trump_suit"): game.trump_suit=None
        if not hasattr(game, "bid_winner"): game.bid_winner=None
        if not hasattr(game, "bid_amount"): game.bid_amount=0
        if not hasattr(game, "current_bid"): game.current_bid=MIN_BID
        if not hasattr(game, "bidder_turn"): game.bidder_turn=0
        if not hasattr(game, "bid_passed"): game.bid_passed=[False,False]
        if not hasattr(game, "last_bid"): game.last_bid=[0,0]
        if not hasattr(game, "trick_leader"): game.trick_leader=None
        if not hasattr(game, "tricks_won"): game.tricks_won=[0,0]
        if not hasattr(game, "cards_won"): game.cards_won=[[],[]]
        if not hasattr(game, "trick_cards"): game.trick_cards=[]
        if not hasattr(game, "trick_num"): game.trick_num=0
        if not hasattr(game, "led_suit"): game.led_suit=None
        if not hasattr(game, "discard_selected"): game.discard_selected=set()
        if not hasattr(game, "trick_pile_count"): game.trick_pile_count=[0,0]
        if not hasattr(game, "score_deltas"): game.score_deltas=[0,0]
        if not hasattr(game, "round_points"): game.round_points=[0,0]
        if not hasattr(game, "bonus_msg"): game.bonus_msg=""

    def _serialize_tracker(self):
        """Serialize card-tracker knowledge so /save captures all known information."""
        t=self.ai.tracker
        return {
            "played": sorted(list(t.played)),
            "my_hand": sorted(list(t.my_hand)),
            "my_piles_visible": sorted(list(t.my_piles_visible)),
            "opp_piles_visible": sorted(list(t.opp_piles_visible)),
            "discarded": sorted(list(t.discarded)),
            "trick_history": [_trick_to_data(tr) for tr in t.trick_history],
            "current_trick": _trick_to_data(t.current_trick),
            "void_suits": [sorted(list(v)) for v in t.void_suits],
        }

    def _deserialize_tracker(self, payload):
        """Restore card-tracker knowledge from snapshot payload."""
        t=self.ai.tracker
        payload=payload or {}
        t.played=set(_to_int(x, 0) for x in payload.get("played", []))
        t.my_hand=set(_to_int(x, 0) for x in payload.get("my_hand", []))
        t.my_piles_visible=set(_to_int(x, 0) for x in payload.get("my_piles_visible", []))
        t.opp_piles_visible=set(_to_int(x, 0) for x in payload.get("opp_piles_visible", []))
        t.discarded=set(_to_int(x, 0) for x in payload.get("discarded", []))
        t.trick_history=[_trick_from_data(tr) for tr in payload.get("trick_history", [])]
        t.current_trick=_trick_from_data(payload.get("current_trick", []))
        void_src=payload.get("void_suits", [[], []])
        if len(void_src)<2: void_src=[[], []]
        t.void_suits=[set(void_src[0]), set(void_src[1])]

    def _build_snapshot(self, reason="manual"):
        """Serialize full current runtime state into one JSON-safe snapshot."""
        g=self.game
        self._ensure_game_runtime_defaults(g)
        clock={
            "initial": [float(g.clock.initial[0]), float(g.clock.initial[1])],
            "rem": [float(g.clock.rem[0]), float(g.clock.rem[1])],
            "active": g.clock.active,
            "flagged": [bool(g.clock.flagged[0]), bool(g.clock.flagged[1])],
        }
        game_state={
            "match_target": _to_int(g.match_target, 1000),
            "scores": [_to_int(g.scores[0], 0), _to_int(g.scores[1], 0)],
            "round_num": _to_int(g.round_num, 0),
            "first_dealer": _to_int(g.first_dealer, 0),
            "state": g.state.name if isinstance(g.state, State) else str(g.state),
            "clock": clock,
            "message": g.message,
            "sub_message": g.sub_message,
            "match_winner": g.match_winner,
            "auto_timer": _to_int(g.auto_timer, 0),
            "shelem_player": g.shelem_player,
            "shelem_start": _to_int(g.shelem_start, 0),
            "hands": [_cards_to_data(g.hands[0]), _cards_to_data(g.hands[1])],
            "special_pile": _cards_to_data(g.special_pile),
            "piles": [_piles_to_data(g.piles[0]), _piles_to_data(g.piles[1])],
            "trump_suit": g.trump_suit,
            "bid_winner": g.bid_winner,
            "bid_amount": _to_int(g.bid_amount, 0),
            "current_bid": _to_int(g.current_bid, MIN_BID),
            "bidder_turn": _to_int(g.bidder_turn, 0),
            "bid_passed": [bool(g.bid_passed[0]), bool(g.bid_passed[1])],
            "last_bid": [_to_int(g.last_bid[0], 0), _to_int(g.last_bid[1], 0)],
            "trick_leader": g.trick_leader,
            "tricks_won": [_to_int(g.tricks_won[0], 0), _to_int(g.tricks_won[1], 0)],
            "cards_won": [_cards_to_data(g.cards_won[0]), _cards_to_data(g.cards_won[1])],
            "trick_cards": _trick_to_data(g.trick_cards),
            "trick_num": _to_int(g.trick_num, 0),
            "led_suit": g.led_suit,
            "discard_selected": sorted(list(g.discard_selected)),
            "trick_pile_count": [_to_int(g.trick_pile_count[0], 0), _to_int(g.trick_pile_count[1], 0)],
            "score_deltas": [_to_int(g.score_deltas[0], 0), _to_int(g.score_deltas[1], 0)],
            "round_points": [_to_int(g.round_points[0], 0), _to_int(g.round_points[1], 0)],
            "bonus_msg": g.bonus_msg,
        }
        ai_round_feat=self.ai.round_bid_feat
        if hasattr(ai_round_feat, "tolist"):
            ai_round_feat=ai_round_feat.tolist()
        return {
            "version": SNAPSHOT_SCHEMA_VERSION,
            "created_at": int(_time.time()),
            "reason": reason,
            "game": game_state,
            "tracker": self._serialize_tracker(),
            "app": {
                "time_minutes": _to_int(self.time_minutes, 10),
                "match_target": _to_int(self.match_target, 1000),
                "bid_value": _to_int(self.bid_value, MIN_BID),
                "show_history": bool(self.show_history),
                "show_played": bool(self.show_played),
                "show_analysis": bool(self.show_analysis),
                "show_ai_hand": bool(self.show_ai_hand),
                "ai_pending": bool(self.ai_pending),
                "ai_delay_left_ms": max(0, _to_int(self.ai_action_time-self.tick, 0)),
                "fan_played": bool(self.fan_played),
                "terminal_lines": list(self.terminal_lines)[-400:],
                "terminal_history": list(self.terminal_history),
                "terminal_scroll": max(0, _to_int(self.terminal_scroll, 0)),
                "terminal_announced_game_id": _to_int(self._terminal_announced_game_id, 0)
                    if self._terminal_announced_game_id is not None else None,
                "terminal_last_round_summary": list(self._terminal_last_round_summary)
                    if self._terminal_last_round_summary is not None else None,
                "terminal_last_match_summary": list(self._terminal_last_match_summary)
                    if self._terminal_last_match_summary is not None else None,
                "jarvis_voice_next_tick": max(0, _to_int(self._jarvis_voice_next_tick, 0)),
                "jarvis_voice_last_key": list(self._jarvis_voice_last_key)
                    if isinstance(self._jarvis_voice_last_key, tuple) else self._jarvis_voice_last_key,
            },
            "ai": {
                "epsilon": float(self.ai.epsilon),
                "games_played": _to_int(self.ai.games_played, 0),
                "round_bid_feat": ai_round_feat,
                "round_bid_amount": _to_int(self.ai.round_bid_amount, 0),
                "last_analysis": [
                    [str(x[0]), float(x[1]), float(x[2]), float(x[3]), float(x[4])]
                    for x in self.ai.last_analysis
                ],
                "last_pv": list(self.ai.last_pv),
                "last_tactics": list(self.ai.last_tactics),
            },
        }

    def _snapshot_fingerprint(self, snapshot):
        """Stable representation used to avoid duplicate timeline inserts per frame."""
        game=snapshot.get("game") or {}
        clock=game.get("clock") or {}
        compact_game={k:v for k,v in game.items() if k!="clock"}
        compact_game["clock"]={
            "initial": clock.get("initial"),
            "active": clock.get("active"),
            "flagged": clock.get("flagged"),
        }
        core={"game": compact_game, "tracker": snapshot.get("tracker")}
        return json.dumps(core, sort_keys=True, separators=(",", ":"), ensure_ascii=True)

    def _apply_snapshot(self, snapshot, track_origin=None,
                        source_save_id=None, source_game_id=None, source_state_num=None):
        """Load a serialized snapshot into the current running application."""
        if not isinstance(snapshot, dict):
            self._terminal_log("Invalid snapshot payload.")
            return False
        game_data=snapshot.get("game") or {}
        g=ShelemGame(_to_int(game_data.get("match_target", self.match_target), self.match_target))
        g.match_target=_to_int(game_data.get("match_target", g.match_target), g.match_target)
        g.scores=[_to_int((game_data.get("scores") or [0,0])[0], 0),
                  _to_int((game_data.get("scores") or [0,0])[1], 0)]
        g.round_num=_to_int(game_data.get("round_num", 0), 0)
        g.first_dealer=_to_int(game_data.get("first_dealer", 0), 0)
        st_name=str(game_data.get("state", State.MATCH_START.name))
        g.state=State[st_name] if st_name in State.__members__ else State.MATCH_START
        clock_data=game_data.get("clock") or {}
        init=clock_data.get("initial") or [600,600]
        rem=clock_data.get("rem") or init
        g.clock.reset(float(init[0]), float(init[1]))
        g.clock.rem=[float(rem[0]), float(rem[1])]
        g.clock.flagged=[bool((clock_data.get("flagged") or [False,False])[0]),
                         bool((clock_data.get("flagged") or [False,False])[1])]
        active=clock_data.get("active", None)
        g.clock.active=active if active in (0,1) else None
        g.clock._t=_time.monotonic() if g.clock.active is not None else None
        g.message=game_data.get("message", "")
        g.sub_message=game_data.get("sub_message", "")
        g.match_winner=game_data.get("match_winner", None)
        g.auto_timer=_to_int(game_data.get("auto_timer", 0), 0)
        g.shelem_player=game_data.get("shelem_player", None)
        g.shelem_start=_to_int(game_data.get("shelem_start", 0), 0)
        hands=game_data.get("hands") or [[],[]]
        g.hands=[_cards_from_data(hands[0] if len(hands)>0 else []),
                 _cards_from_data(hands[1] if len(hands)>1 else [])]
        g.special_pile=_cards_from_data(game_data.get("special_pile", []))
        piles=game_data.get("piles") or [[],[]]
        g.piles=[_piles_from_data(piles[0] if len(piles)>0 else []),
                 _piles_from_data(piles[1] if len(piles)>1 else [])]
        g.trump_suit=game_data.get("trump_suit", None)
        g.bid_winner=game_data.get("bid_winner", None)
        g.bid_amount=_to_int(game_data.get("bid_amount", 0), 0)
        g.current_bid=_to_int(game_data.get("current_bid", MIN_BID), MIN_BID)
        g.bidder_turn=_to_int(game_data.get("bidder_turn", 0), 0)
        bid_passed=game_data.get("bid_passed") or [False,False]
        g.bid_passed=[bool(bid_passed[0]), bool(bid_passed[1] if len(bid_passed)>1 else False)]
        last_bid=game_data.get("last_bid") or [0,0]
        g.last_bid=[_to_int(last_bid[0], 0), _to_int(last_bid[1] if len(last_bid)>1 else 0, 0)]
        g.trick_leader=game_data.get("trick_leader", None)
        tricks_won=game_data.get("tricks_won") or [0,0]
        g.tricks_won=[_to_int(tricks_won[0], 0), _to_int(tricks_won[1] if len(tricks_won)>1 else 0, 0)]
        cards_won=game_data.get("cards_won") or [[],[]]
        g.cards_won=[_cards_from_data(cards_won[0] if len(cards_won)>0 else []),
                     _cards_from_data(cards_won[1] if len(cards_won)>1 else [])]
        g.trick_cards=_trick_from_data(game_data.get("trick_cards", []))
        g.trick_num=_to_int(game_data.get("trick_num", 0), 0)
        g.led_suit=game_data.get("led_suit", None)
        g.discard_selected=set(_to_int(x, 0) for x in game_data.get("discard_selected", []))
        tpc=game_data.get("trick_pile_count") or [0,0]
        g.trick_pile_count=[_to_int(tpc[0], 0), _to_int(tpc[1] if len(tpc)>1 else 0, 0)]
        deltas=game_data.get("score_deltas") or [0,0]
        g.score_deltas=[_to_int(deltas[0], 0), _to_int(deltas[1] if len(deltas)>1 else 0, 0)]
        rpts=game_data.get("round_points") or [0,0]
        g.round_points=[_to_int(rpts[0], 0), _to_int(rpts[1] if len(rpts)>1 else 0, 0)]
        g.bonus_msg=game_data.get("bonus_msg", "")
        self._ensure_game_runtime_defaults(g)
        self.game=g
        self._terminal_last_status=None
        self._terminal_last_round_summary=None
        self._terminal_last_match_summary=None
        self._jarvis_voice_last_key=None
        self._jarvis_voice_next_tick=0
        self._flavor_last_key=None
        self._flavor_next_tick=0
                                               
        app_state=snapshot.get("app") or {}
        self.time_minutes=max(1, _to_int(app_state.get("time_minutes", self.time_minutes), self.time_minutes))
        self.match_target=max(200, _to_int(app_state.get("match_target", self.match_target), self.match_target))
        self.bid_value=_to_int(app_state.get("bid_value", self.bid_value), self.bid_value)
        self.show_history=bool(app_state.get("show_history", self.show_history))
        self.show_played=bool(app_state.get("show_played", self.show_played))
        self.show_analysis=bool(app_state.get("show_analysis", self.show_analysis))
        self.show_ai_hand=bool(app_state.get("show_ai_hand", self.show_ai_hand))
        self.ai_pending=bool(app_state.get("ai_pending", False))
        delay_left=_to_int(app_state.get("ai_delay_left_ms", 0), 0)
        self.ai_action_time=pygame.time.get_ticks()+max(0, delay_left)
        self.fan_played=bool(app_state.get("fan_played", False))
        if isinstance(app_state.get("terminal_lines"), list):
            restored=[]
            for item in app_state.get("terminal_lines", []):
                ent=self._terminal_entry(item)
                restored.append({
                    "text": ent["text"],
                    "color": [ent["color"][0], ent["color"][1], ent["color"][2]],
                    "suit_colors": bool(ent.get("suit_colors", True)),
                })
            self.terminal_lines=deque(restored, maxlen=self.terminal_lines.maxlen)
        if isinstance(app_state.get("terminal_history"), list):
            self.terminal_history=deque((str(x) for x in app_state.get("terminal_history", [])),
                                        maxlen=self.terminal_history.maxlen)
        self.terminal_scroll=max(0, _to_int(app_state.get("terminal_scroll", self.terminal_scroll), 0))
        self.terminal_scroll_max=0
        gid_saved=app_state.get("terminal_announced_game_id", None)
        self._terminal_announced_game_id=_to_int(gid_saved, 0) if gid_saved is not None else None
        rs_saved=app_state.get("terminal_last_round_summary")
        self._terminal_last_round_summary=tuple(rs_saved) if isinstance(rs_saved, list) else None
        ms_saved=app_state.get("terminal_last_match_summary")
        self._terminal_last_match_summary=tuple(ms_saved) if isinstance(ms_saved, list) else None
        self._jarvis_voice_next_tick=max(0, _to_int(app_state.get("jarvis_voice_next_tick", 0), 0))
        jv_key=app_state.get("jarvis_voice_last_key", None)
        self._jarvis_voice_last_key=tuple(jv_key) if isinstance(jv_key, list) else jv_key
        self.terminal_hist_index=None
        self.terminal_hist_draft=""
        self.tactic_grade_open=False
        self.tactic_grade_target=None
        self.tactic_grade_buttons={}
                                                               
        self._deserialize_tracker(snapshot.get("tracker") or {})
        ai_state=snapshot.get("ai") or {}
        self.ai.epsilon=float(ai_state.get("epsilon", self.ai.epsilon))
        self.ai.games_played=_to_int(ai_state.get("games_played", self.ai.games_played), self.ai.games_played)
        self.ai.round_bid_amount=_to_int(ai_state.get("round_bid_amount", 0), 0)
        self.ai.round_bid_feat=None
        self.ai.last_analysis=[tuple(x) for x in ai_state.get("last_analysis", self.ai.last_analysis)]
        self.ai.last_pv=list(ai_state.get("last_pv", self.ai.last_pv))
        self.ai.last_tactics=list(ai_state.get("last_tactics", self.ai.last_tactics))
        self.ai.round_decisions=[]
        self.ai._bg_result=None; self.ai._bg_state=None; self.ai._bg_key=None
        if track_origin and not self.replay_mode:
            self._begin_timeline_game(
                track_origin,
                source_save_id=source_save_id,
                source_game_id=source_game_id,
                source_state_num=source_state_num,
            )
        return True

    def _begin_timeline_game(self, origin, source_save_id=None, source_game_id=None, source_state_num=None):
        """Start timeline recording for a new/loaded playable game."""
        if self.replay_mode:
            return
        self._reset_timeline_nav()
        self.timeline_game_id=self.timeline_store.create_game(
            self.match_target,
            self.time_minutes,
            origin,
            source_save_id=source_save_id,
            source_game_id=source_game_id,
            source_state_num=source_state_num,
        )
        self.timeline_state_num=0
        self.timeline_last_fp=None
        self.timeline_last_fast_sig=None
        self.timeline_last_tick_ms=0
        self._terminal_last_status=None
        self._terminal_announced_game_id=None
        self._terminal_last_round_summary=None
        self._terminal_last_match_summary=None
        self._jarvis_voice_last_key=None
        self._jarvis_voice_next_tick=0
        self._flavor_last_key=None
        self._flavor_next_tick=0
        self._record_timeline_state("start", force=True)

    def _timeline_fast_signature(self):
        """Cheap change detector used before costly snapshot serialization."""
        g=self.game
        self._ensure_game_runtime_defaults(g)
        state_name=g.state.name if isinstance(g.state, State) else str(g.state)
        hands=g.hands if isinstance(g.hands, list) and len(g.hands)>=2 else [[], []]
        piles=g.piles if isinstance(g.piles, list) and len(g.piles)>=2 else [[[], [], [], []], [[], [], [], []]]
        pile_sizes=[]
        for p in (0, 1):
            row=piles[p] if p<len(piles) else []
            for i in range(4):
                pile=row[i] if i<len(row) else []
                pile_sizes.append(len(pile))
        trick_cards=tuple((c.rank, c.suit, _to_int(pl, 0)) for c,pl in (g.trick_cards or []))
        return (
            state_name,
            _to_int(g.round_num, 0),
            _to_int(g.trick_num, 0),
            g.trump_suit,
            g.bid_winner,
            _to_int(g.bid_amount, 0),
            _to_int(g.current_bid, MIN_BID),
            _to_int(g.bidder_turn, 0),
            tuple(bool(x) for x in (g.bid_passed or [False, False])[:2]),
            tuple(_to_int(x, 0) for x in (g.last_bid or [0, 0])[:2]),
            g.trick_leader,
            tuple(_to_int(x, 0) for x in (g.scores or [0, 0])[:2]),
            tuple(_to_int(x, 0) for x in (g.tricks_won or [0, 0])[:2]),
            tuple(len(hands[p]) if p<len(hands) else 0 for p in (0, 1)),
            tuple(pile_sizes),
            trick_cards,
            tuple(_to_int(x, 0) for x in (g.trick_pile_count or [0, 0])[:2]),
            tuple(_to_int(x, 0) for x in (g.round_points or [0, 0])[:2]),
            tuple(_to_int(x, 0) for x in (g.score_deltas or [0, 0])[:2]),
            tuple(sorted(_to_int(x, 0) for x in (g.discard_selected or []))),
            g.match_winner,
        )

    def _record_timeline_state(self, reason="auto", force=False):
        """Append current snapshot into game timeline if state actually changed."""
        if self.replay_mode or self.timeline_game_id is None:
            return
        if self.timeline_nav_active:
            return
        fast_sig=None
        if reason=="tick" and not force:
            now_ms=max(0, _to_int(self.tick, 0))
            if now_ms-self.timeline_last_tick_ms<TIMELINE_TICK_MIN_MS:
                return
            fast_sig=self._timeline_fast_signature()
            if fast_sig==self.timeline_last_fast_sig:
                return
        snapshot=self._build_snapshot(reason=reason)
        fp=self._snapshot_fingerprint(snapshot)
        if (not force) and fp==self.timeline_last_fp:
            if fast_sig is None:
                fast_sig=self._timeline_fast_signature()
            self.timeline_last_fast_sig=fast_sig
            return
        self.timeline_state_num+=1
        self.timeline_store.append_state(self.timeline_game_id, self.timeline_state_num, snapshot, reason=reason)
        self.timeline_store.update_game_progress(self.timeline_game_id, snapshot)
        if self.timeline_nav_states and self.timeline_nav_states[-1][0]>=self.timeline_state_num:
            self.timeline_nav_states=[]
        self.timeline_nav_states.append((self.timeline_state_num, snapshot))
        self.timeline_nav_live_index=max(0, len(self.timeline_nav_states)-1)
        if not self.timeline_nav_active:
            self.timeline_nav_index=self.timeline_nav_live_index
        self.timeline_last_fp=fp
        if fast_sig is None:
            fast_sig=self._timeline_fast_signature()
        self.timeline_last_fast_sig=fast_sig
        if reason=="tick":
            self.timeline_last_tick_ms=max(0, _to_int(self.tick, 0))

    def _start_new_match_from_setup(self):
        """Start a brand-new match from current setup options."""
        secs=self.time_minutes*60
        self.game=ShelemGame(self.match_target); self.game.clock.reset(secs,secs)
        self.game.new_round(); self.ai.new_round(self.game.hands[AI_PLAYER])
        self.bid_value=MIN_BID; self.show_history=False; self.show_played=False
        self._terminal_last_status=None
        self._terminal_announced_game_id=None
        self._terminal_last_round_summary=None
        self._terminal_last_match_summary=None
        self._jarvis_voice_last_key=None
        self._jarvis_voice_next_tick=0
        self._flavor_last_key=None
        self._flavor_next_tick=0
        self._begin_timeline_game("new_match")

    def _refresh_db_inspector(self):
        """Reload game list shown inside /inspect_db window."""
        self.db_inspector_items=self.timeline_store.list_games(limit=400)
        self.db_inspector_scroll=max(0, min(self.db_inspector_scroll, max(0, len(self.db_inspector_items)-1)))

    def _launch_replay_window(self, game_id, state_num=1):
        """Open replay viewer in a separate process/window."""
        try:
            cmd=[sys.executable, os.path.abspath(__file__), "--replay-game", str(_to_int(game_id, 0)),
                 "--replay-state", str(max(1, _to_int(state_num, 1)))]
            subprocess.Popen(cmd)
            self._terminal_log(f"Opened replay window for game #{_to_int(game_id, 0)}.")
        except Exception as ex:
            self._terminal_log(f"Failed to open replay window: {ex}")

    def _init_replay_session(self, game_id, state_num):
        """Initialize read-only replay session from timeline DB."""
        if game_id is None:
            self._terminal_log("Replay mode missing game id.")
            return
        states=self.timeline_store.load_game_states(game_id)
        if not states:
            self._terminal_log(f"Replay game #{game_id} not found.")
            return
        self.replay_states=states
        target=max(1, _to_int(state_num, 1))
        idx=0
        for i,(sn,_) in enumerate(states):
            if sn>=target:
                idx=i
                break
            idx=i
        self.replay_index=idx
        self._apply_snapshot(states[idx][1], track_origin=None)
        self.terminal_active=False
        self.db_inspector_open=False
        self._terminal_log(f"Replay game #{game_id} loaded ({len(states)} states).")

    def _replay_jump(self, delta):
        """Move replay cursor backward/forward through recorded states."""
        if not self.replay_mode or not self.replay_states:
            return
        ni=max(0, min(len(self.replay_states)-1, self.replay_index+delta))
        if ni==self.replay_index:
            return
        self.replay_index=ni
        self._apply_snapshot(self.replay_states[self.replay_index][1], track_origin=None)

    def _reset_timeline_nav(self):
        """Reset in-game back/forward timeline navigation state."""
        self.timeline_nav_active=False
        self.timeline_nav_states=[]
        self.timeline_nav_index=0
        self.timeline_nav_live_index=0
        self.tactic_grade_open=False
        self.tactic_grade_target=None
        self.tactic_grade_buttons={}

    def _timeline_nav_anchor_indices(self, states):
        """Return timeline indices that represent trick/round milestones."""
        if not states:
            return []
        anchors_by_key={}
        for idx,(_sn,snap) in enumerate(states):
            game_data=(snap or {}).get("game") or {}
            st_name=str(game_data.get("state", ""))
            rnum=_to_int(game_data.get("round_num", 0), 0)
            tnum=_to_int(game_data.get("trick_num", 0), 0)
            key=None
            if st_name=="TRICK_RESULT" and rnum>0 and tnum>0:
                key=("trick", rnum, tnum)
            elif st_name=="ROUND_END" and rnum>0:
                key=("round_end", rnum)
            elif st_name=="MATCH_OVER":
                key=("match_over", max(0, rnum))
            if key is not None:
                anchors_by_key[key]=idx
        anchors=sorted(set(anchors_by_key.values()))
        if not anchors:
            anchors=[0]
        live=max(0, len(states)-1)
        if anchors[-1]!=live:
            anchors.append(live)
        return anchors

    def _timeline_nav_load_states(self):
        """Load current game's timeline states for in-game stepping UI."""
        if self.replay_mode or self.timeline_game_id is None:
            return []
        gid=_to_int(self.timeline_game_id, 0)
        if gid<=0:
            return []
        if self.timeline_nav_states and self.timeline_state_num>0 and len(self.timeline_nav_states)>=self.timeline_state_num:
            live=max(0, len(self.timeline_nav_states)-1)
            self.timeline_nav_live_index=live
            self.timeline_nav_index=max(0, min(self.timeline_nav_index, live))
            return self.timeline_nav_states
        states=self.timeline_store.load_game_states(gid)
        self.timeline_nav_states=list(states or [])
        if not self.timeline_nav_states:
            self.timeline_nav_index=0
            self.timeline_nav_live_index=0
            return []
        live=len(self.timeline_nav_states)-1
        self.timeline_state_num=max(self.timeline_state_num, _to_int(self.timeline_nav_states[-1][0], 0))
        self.timeline_nav_live_index=max(0, live)
        self.timeline_nav_index=max(0, min(self.timeline_nav_index, live))
        return self.timeline_nav_states

    def _timeline_nav_step(self, delta):
        """Step backward/forward one recorded timeline state."""
        step=-1 if int(delta)<0 else 1
        states=self._timeline_nav_load_states()
        if not states:
            return
        if not self.timeline_nav_active:
            self.timeline_nav_active=True
            self.timeline_nav_index=self.timeline_nav_live_index
        ni=max(0, min(self.timeline_nav_live_index, self.timeline_nav_index+step))
        if ni==self.timeline_nav_index:
            if self.timeline_nav_index>=self.timeline_nav_live_index:
                self.timeline_nav_active=False
            return
        self.timeline_nav_index=ni
        self._apply_snapshot(states[self.timeline_nav_index][1], track_origin=None)
        if self.timeline_nav_index>=self.timeline_nav_live_index:
            self.timeline_nav_index=self.timeline_nav_live_index
            self.timeline_nav_active=False

    def _timeline_nav_jump_live(self):
        """Jump from history view back to latest recorded live state."""
        states=self._timeline_nav_load_states()
        if not states:
            return
        live=max(0, self.timeline_nav_live_index)
        if not self.timeline_nav_active and self.timeline_nav_index>=live:
            return
        self.timeline_nav_index=live
        self._apply_snapshot(states[live][1], track_origin=None)
        self.timeline_nav_active=False

    def _can_grade_last_move(self):
        """Quick check to enable/disable grade-move button."""
        if self.replay_mode or self.timeline_game_id is None:
            return False
        if self.timeline_nav_active:
            return self.timeline_nav_index>0
        return self.timeline_state_num>1

    def _state_code_from_snapshot(self, snapshot, game_id=None):
        """Compute compact state code for an arbitrary snapshot."""
        game_data=(snapshot or {}).get("game") or {}
        st_name=str(game_data.get("state", ""))
        trick=_to_int(game_data.get("trick_num", 0), 0)
        play_phase={
            "PLAY_HAND_LEADER": 1,
            "PLAY_HAND_FOLLOWER": 2,
            "PLAY_PILE_LEADER": 3,
            "PLAY_PILE_FOLLOWER": 4,
            "TRICK_RESULT": 5,
        }
        if st_name in play_phase:
            tb=max(1, trick)
            ph=play_phase[st_name]
        else:
            pre_phase={
                "MATCH_START": (-3, 0),
                "BIDDING": (-2, 0),
                "TAKE_SPECIAL": (-2, 1),
                "DISCARDING": (-2, 2),
                "TRUMP_SELECT": (-2, 3),
                "ROUND_END": (-1, 0),
                "SHELEM_CELEBRATION": (-1, 1),
                "MATCH_OVER": (0, 0),
            }
            tb,ph=pre_phase.get(st_name, (0, 0))
        gid=game_id if game_id is not None else self._current_game_id()
        gtxt=str(gid) if gid is not None else "?"
        return f"{gtxt}.{tb}.{ph}"

    def _build_tactic_grade_target(self):
        """Resolve (previous -> current) timeline transition for grading."""
        states=self._timeline_nav_load_states()
        if not states:
            return None
        to_idx=self.timeline_nav_index if self.timeline_nav_active else self.timeline_nav_live_index
        to_idx=max(0, min(to_idx, len(states)-1))
        if to_idx<=0:
            return None
        to_sn,to_snap=states[to_idx]
        to_fp=self._snapshot_fingerprint(to_snap or {})
        from_idx=to_idx-1
        while from_idx>=0:
            _,cand_snap=states[from_idx]
            if self._snapshot_fingerprint(cand_snap or {})!=to_fp:
                break
            from_idx-=1
        if from_idx<0:
            return None
        from_sn,from_snap=states[from_idx]
        gid=_to_int(self.timeline_game_id, 0)
        if gid<=0:
            return None
        game_data=(to_snap or {}).get("game") or {}
        prev_data=(from_snap or {}).get("game") or {}
        actor=None
        trick_cards=game_data.get("trick_cards") or []
        if trick_cards:
            tail=trick_cards[-1]
            if isinstance(tail, dict):
                p=_to_int(tail.get("player", -1), -1)
                actor=p if p in (HUMAN, AI_PLAYER) else None
        if actor is None and str(game_data.get("state", ""))=="BIDDING":
            p=_to_int(game_data.get("bidder_turn", -1), -1)
            actor=p if p in (HUMAN, AI_PLAYER) else None
        move_summary=(
            f"{str(prev_data.get('state', '?'))} -> {str(game_data.get('state', '?'))} | "
            f"R{_to_int(game_data.get('round_num', 0), 0)} T{_to_int(game_data.get('trick_num', 0), 0)}"
        )
        return {
            "game_id": gid,
            "from_state_num": _to_int(from_sn, 0),
            "to_state_num": _to_int(to_sn, 0),
            "from_snapshot": from_snap,
            "to_snapshot": to_snap,
            "state_code": self._state_code_from_snapshot(to_snap, game_id=gid),
            "round_num": _to_int(game_data.get("round_num", 0), 0),
            "trick_num": _to_int(game_data.get("trick_num", 0), 0),
            "fsm_state": str(game_data.get("state", "")),
            "actor": actor,
            "bid_amount": _to_int(game_data.get("bid_amount", 0), 0),
            "bid_winner": game_data.get("bid_winner", None),
            "trump_suit": game_data.get("trump_suit", None),
            "score_a": _to_int((game_data.get("scores") or [0, 0])[0], 0),
            "score_b": _to_int((game_data.get("scores") or [0, 0])[1], 0),
            "move_summary": move_summary,
            "source_mode": "history" if self.timeline_nav_active else "live",
        }

    def _open_tactic_grade_modal(self):
        """Open grade modal targeted at the latest resolved move transition."""
        target=self._build_tactic_grade_target()
        if target is None:
            self._terminal_log("No completed move transition available to grade yet.")
            return
        self.tactic_grade_target=target
        self.tactic_grade_open=True
        self.tactic_grade_buttons={}

    def _close_tactic_grade_modal(self):
        self.tactic_grade_open=False
        self.tactic_grade_target=None
        self.tactic_grade_buttons={}

    def _save_tactic_grade(self, grade):
        """Persist one user grade into dedicated tactics database."""
        target=self.tactic_grade_target or self._build_tactic_grade_target()
        if not target:
            self._terminal_log("Could not resolve target move for grading.")
            self._close_tactic_grade_modal()
            return
        grade_key=str(grade or "").strip().lower()
        try:
            rid=self.tactic_store.save_grade({
                "game_id": target.get("game_id"),
                "from_state_num": target.get("from_state_num"),
                "to_state_num": target.get("to_state_num"),
                "state_code": target.get("state_code"),
                "round_num": target.get("round_num"),
                "trick_num": target.get("trick_num"),
                "fsm_state": target.get("fsm_state"),
                "actor": target.get("actor"),
                "bid_amount": target.get("bid_amount"),
                "bid_winner": target.get("bid_winner"),
                "trump_suit": target.get("trump_suit"),
                "score_a": target.get("score_a"),
                "score_b": target.get("score_b"),
                "grade": grade_key,
                "source_mode": target.get("source_mode"),
                "move_summary": target.get("move_summary"),
                "from_snapshot": target.get("from_snapshot"),
                "to_snapshot": target.get("to_snapshot"),
            })
            self._terminal_log(
                f"Tactic saved #{rid}: {grade_key.title()} | game #{target['game_id']} "
                f"state {target['from_state_num']} -> {target['to_state_num']}."
            )
        except Exception as ex:
            self._terminal_log(f"Failed to save tactic grade: {ex}")
        self._close_tactic_grade_modal()

    def _log_tactics(self, limit=12):
        """Emit compact tactics DB summary + recent graded moves."""
        lim=max(1, min(80, _to_int(limit, 12)))
        counts=self.tactic_store.grade_summary()
        self._terminal_log(
            "Tactics DB "
            f"({TACTICS_DB_FILE}): "
            f"Bad {counts.get('bad',0)} | Neutral {counts.get('neutral',0)} | "
            f"Good {counts.get('good',0)} | Excellent {counts.get('excellent',0)}"
        )
        rows=self.tactic_store.list_recent(limit=lim)
        if not rows:
            self._terminal_log("No graded tactics yet.")
            return
        for r in rows:
            gid=_to_int(r.get("game_id", 0), 0)
            fr=_to_int(r.get("from_state_num", 0), 0)
            to=_to_int(r.get("to_state_num", 0), 0)
            grade=str(r.get("grade", "?")).strip().title()
            code=str(r.get("state_code", "?"))
            summary=str(r.get("move_summary", "")).strip()
            self._terminal_log(f"#{_to_int(r.get('id',0),0)} {grade}  G{gid} {fr}->{to}  {code}  {summary}")

    def _execute_terminal_command(self, raw_cmd):
        """Parse and execute one slash command entered in terminal."""
        cmd=(raw_cmd or "").strip()
        if not cmd:
            return
        self.terminal_scroll=0
        self._terminal_log(f"> {cmd}")
        try:
            parts=cmd.split()
            op=parts[0].lower()
            if op=="/save":
                sid=self.save_store.save_snapshot(self._build_snapshot(reason="manual_save"))
                self._terminal_log(f"Saved current state as #{sid}.")
                return
            if op=="/history":
                self._log_round_history()
                return
            if op=="/played":
                self._log_played_cards()
                return
            if op=="/inspect_db":
                self.db_inspector_open=True
                self._refresh_db_inspector()
                self._terminal_log("Opened game database inspector.")
                return
            if op=="/tactics":
                lim=_to_int(parts[1], 12) if len(parts)>=2 else 12
                self._log_tactics(lim)
                return
            if op=="/load":
                if len(parts)==2:
                    sid=_to_int(parts[1], -1)
                    if sid<=0:
                        self._terminal_log("Usage: /load [number]")
                        return
                    snap=self.save_store.load_snapshot(sid)
                    if not snap:
                        self._terminal_log(f"Save #{sid} not found.")
                        return
                    if self._apply_snapshot(snap, track_origin="load_save", source_save_id=sid):
                        self._terminal_log(f"Loaded save #{sid}.")
                    return
                if len(parts)==5 and parts[1].lower()=="game" and parts[3].lower()=="state":
                    gid=_to_int(parts[2], -1)
                    sn=_to_int(parts[4], -1)
                    if gid<=0 or sn<=0:
                        self._terminal_log("Usage: /load game [number] state [number]")
                        return
                    snap=self.timeline_store.load_game_state(gid, sn)
                    if not snap:
                        self._terminal_log(f"Game #{gid} state #{sn} not found.")
                        return
                    if self._apply_snapshot(
                        snap,
                        track_origin="load_game_state",
                        source_game_id=gid,
                        source_state_num=sn,
                    ):
                        self._terminal_log(f"Loaded game #{gid} state #{sn}.")
                    return
                self._terminal_log("Usage: /load [number]  OR  /load game [number] state [number]")
                return
            self._terminal_log("Unknown command. Try /save, /load, /inspect_db, /history, /played, /tactics [N].")
        finally:
            if not self.replay_mode and self.timeline_game_id is not None:
                self._record_timeline_state("terminal", force=True)

    def _activate_terminal(self, prefix=""):
        """Focus terminal input (optionally seeding a prefix like '/')."""
        self.terminal_active=True
        self.terminal_scroll=0
        if prefix and not self.terminal_input:
            self.terminal_input=prefix
        self.terminal_hist_index=None
        self.terminal_hist_draft=self.terminal_input
        self._terminal_cursor_t=self.tick

    def _handle_terminal_key(self, event):
        """Handle text editing and command submission for terminal input."""
        if not self.terminal_active:
            return False
        if event.key==pygame.K_RETURN:
            cmd=self.terminal_input.strip()
            self._remember_terminal_command(cmd)
            self.terminal_input=""
            self.terminal_active=False
            self._execute_terminal_command(cmd)
            return True
        if event.key==pygame.K_ESCAPE:
            self.terminal_active=False
            self.terminal_hist_index=None
            return True
        if event.key==pygame.K_PAGEUP:
            self.terminal_scroll=max(
                0,
                min(max(0, _to_int(self.terminal_scroll_max, 0)), self.terminal_scroll+5)
            )
            return True
        if event.key==pygame.K_PAGEDOWN:
            self.terminal_scroll=max(
                0,
                min(max(0, _to_int(self.terminal_scroll_max, 0)), self.terminal_scroll-5)
            )
            return True
        if event.key==pygame.K_UP:
            if not self.terminal_history:
                return True
            if self.terminal_hist_index is None:
                self.terminal_hist_draft=self.terminal_input
                self.terminal_hist_index=len(self.terminal_history)-1
            elif self.terminal_hist_index>0:
                self.terminal_hist_index-=1
            self.terminal_input=self.terminal_history[self.terminal_hist_index]
            return True
        if event.key==pygame.K_DOWN:
            if self.terminal_hist_index is None:
                return True
            if self.terminal_hist_index<len(self.terminal_history)-1:
                self.terminal_hist_index+=1
                self.terminal_input=self.terminal_history[self.terminal_hist_index]
            else:
                self.terminal_hist_index=None
                self.terminal_input=self.terminal_hist_draft
            return True
        if event.key==pygame.K_BACKSPACE:
            if self.terminal_hist_index is not None:
                self.terminal_hist_index=None
            self.terminal_input=self.terminal_input[:-1]
            return True
        if event.key==pygame.K_TAB:
            return True
        ch=event.unicode
        if ch and ch.isprintable():
            if self.terminal_hist_index is not None:
                self.terminal_hist_index=None
            self.terminal_input+=ch
            return True
        return False

    def _handle_keydown(self, event):
        """Centralized key handling for terminal, replay, and gameplay setup."""
                                            
        if self.terminal_active and self._handle_terminal_key(event):
            return
        if self.tactic_grade_open:
            if event.key==pygame.K_ESCAPE:
                self._close_tactic_grade_modal()
            return
                                          
        if event.key==pygame.K_SLASH and not self.terminal_active:
            self._activate_terminal(prefix="/")
            return
                          
        if self.replay_mode:
            if event.key==pygame.K_LEFT: self._replay_jump(-1); return
            if event.key==pygame.K_RIGHT: self._replay_jump(+1); return
            if event.key==pygame.K_ESCAPE: self._quit(); return
            return
                                   
        if self.db_inspector_open:
            if event.key in (pygame.K_UP, pygame.K_PAGEUP):
                self.db_inspector_scroll=max(0, self.db_inspector_scroll-1)
                return
            if event.key in (pygame.K_DOWN, pygame.K_PAGEDOWN):
                self.db_inspector_scroll=min(max(0, len(self.db_inspector_items)-1), self.db_inspector_scroll+1)
                return
            if event.key==pygame.K_ESCAPE:
                self.db_inspector_open=False
                return
                                                  
        if event.key==pygame.K_ESCAPE:
            self._quit()
            return
                                                                              
        if self.game.state==State.MATCH_START:
            self._setup_key(event)

                                                                                                                                                      
    def run(self):
                                                                                                                                                                          
        """Main game loop: process input, advance logic, then draw frame."""
                                                                                                                                          
        while True:
                                                                                                                                                                           
            mx,my=pygame.mouse.get_pos()
                                                                                                                                                                
            self.vmouse=self.R.virt(mx,my); self.tick=pygame.time.get_ticks()
                                                                                                                                                                          
            for event in pygame.event.get():
                                                                                                                                                                            
                if event.type==pygame.QUIT: self._quit()
                                                                                                                                                              
                elif event.type==pygame.VIDEORESIZE:
                                                                                                                                                                                      
                    self.sw,self.sh=event.w,event.h
                                                                                                                                                                        
                    self.screen=pygame.display.set_mode((self.sw,self.sh),pygame.RESIZABLE)
                                                                                                                                                                        
                    self.R.screen=self.screen; self.R.update_scale(self.sw,self.sh); self.R._fc.clear()
                                                                                                                                                              
                elif event.type==pygame.MOUSEBUTTONDOWN and event.button==1:
                    if self._handle_music_mouse_down(event.pos):
                        continue
                    self._handle_click(event.pos)
                elif event.type==pygame.MOUSEBUTTONUP and event.button==1:
                    self.music_dragging=False
                elif event.type==pygame.MOUSEMOTION and self.music_dragging:
                    self._update_music_volume_from_screen_x(event.pos[0])
                elif event.type==pygame.MOUSEWHEEL:
                    if self.db_inspector_open:
                        self.db_inspector_scroll=max(
                            0,
                            min(max(0, len(self.db_inspector_items)-1), self.db_inspector_scroll-event.y)
                        )
                    elif self.terminal_panel_rect and self.terminal_panel_rect.collidepoint(pygame.mouse.get_pos()):
                        self.terminal_scroll=max(
                            0,
                            min(max(0, _to_int(self.terminal_scroll_max, 0)), self.terminal_scroll+event.y)
                        )
                elif self.music_end_event is not None and event.type==self.music_end_event:
                    self._on_music_track_end()
                                                                                                                                                              
                elif event.type==pygame.KEYDOWN: self._handle_keydown(event)
                                                       
            if not self.replay_mode:
                if (not self.tactic_grade_open) and (not self.timeline_nav_active):
                    self.game.clock.update()
                if (not self.timeline_nav_active) and (not self.tactic_grade_open):
                    if self.game.check_timeout():
                        self._queue_payout_sounds(self.game.score_deltas)
                    self.ai.sync_background(self.game)
                    self._auto_advance(); self._ai_tick()
                    self._tick_stu_ungar()
                    self._record_timeline_state("tick")
            self._update_background_music()
            self._tick_payout_sounds()
                                                                                                                                                                
            self._draw(); pygame.display.flip(); self.clock_tick.tick(FPS)

                                                                                                                                                      
    def _quit(self):
                                                                                                                                                                          
        """Persist models/history and exit the application."""
                                                                                                                                                            
        self.ai.shutdown()
                                                                                                                                                            
        if not self.replay_mode:
            self.ai.save(); self.save_history()
        try:
            pygame.mixer.music.stop()
        except Exception:
            pass
        pygame.quit(); sys.exit()

    def _desired_music_mode(self):
        """Pick background loop based on setup/play/danger context."""
        if self.replay_mode:
            return None
        if self.game.state==State.MATCH_START:
            self.jaws_latched_round=None
            return "setup"
        doomed=self._contract_doomed_player()
        if doomed is not None:
            return "requiem"
        if self._danger_music_active():
            return "danger"
        return "gameplay"

    def _danger_music_active(self):
        """Latch danger music once either side's contract becomes very unlikely."""
        g=self.game
        cur_round=_to_int(getattr(g, "round_num", 0), 0)
        if self.jaws_latched_round is not None and cur_round!=self.jaws_latched_round:
            self.jaws_latched_round=None
        if self.jaws_latched_round is not None:
            return True
        if self._human_contract_in_danger() or self._ai_contract_in_danger():
            self.jaws_latched_round=cur_round
            return True
        return False

    def _contract_doomed_player(self):
        """Return bidder id when contract is mathematically impossible, else None."""
        g=self.game
        if g.bid_winner is None or _to_int(g.bid_amount, 0)<=0:
            return None
        if g.state in (State.MATCH_START,State.BIDDING,State.TAKE_SPECIAL,State.DISCARDING,
                       State.TRUMP_SELECT,State.MATCH_OVER):
            return None
        bidder=int(g.bid_winner)
        bid_live=g.live_pts(bidder)
        opp_live=g.live_pts(1-bidder)
        remaining=max(0, TOTAL_PTS-(bid_live+opp_live))
        needed=max(0, _to_int(g.bid_amount, 0)-bid_live)
        if needed<=0:
            return None
        return bidder if needed>remaining else None

    def _bidder_contract_in_danger(self, bidder):
        """Heuristic danger detector for bidder close to failing contract."""
        g=self.game
        if g.bid_winner!=bidder or _to_int(g.bid_amount, 0)<=0:
            return False
        if g.state in (State.MATCH_START,State.BIDDING,State.TAKE_SPECIAL,State.DISCARDING,
                       State.TRUMP_SELECT,State.MATCH_OVER):
            return False
        if _to_int(g.trick_num, 0)<=0:
            return False
        bid_live=g.live_pts(bidder)
        opp_live=g.live_pts(1-bidder)
        remaining=max(0, TOTAL_PTS-(bid_live+opp_live))
        needed=max(0, _to_int(g.bid_amount, 0)-bid_live)
        if needed<=0:
            return False
        if needed>remaining:
            return True
        if needed>=remaining-5:
            return True
        progressed=g.trick_num>=3
        return progressed and needed>=int(remaining*0.82)

    def _human_contract_in_danger(self):
        """Heuristic: human bidder needs almost all remaining round points."""
        return self._bidder_contract_in_danger(HUMAN)

    def _ai_contract_in_danger(self):
        """Heuristic: Jarvis bidder needs almost all remaining round points."""
        return self._bidder_contract_in_danger(AI_PLAYER)

    def _set_music_volume(self, value):
        """Set global music volume multiplier in [0,1] and apply immediately."""
        self.music_volume=max(0.0, min(1.0, float(value)))
        if self.bg_music_mode is not None:
            try:
                base=self.bg_music_vol.get(self.bg_music_mode, 0.42)
                pygame.mixer.music.set_volume(max(0.0, min(1.0, base*self.music_volume)))
            except Exception:
                pass

    def _update_music_volume_from_screen_x(self, sx):
        """Map pointer x-position onto current music slider range."""
        if self.music_track_rect is None:
            return
        span=max(1, self.music_track_rect.w)
        rel=(float(sx)-self.music_track_rect.x)/float(span)
        self._set_music_volume(rel)

    def _music_track_keys_for_mode(self, mode):
        """Return ordered music asset keys for a given background mode."""
        if mode=="gameplay":
            return ["gameplay_music", "gameplay_music_alt"]
        if mode=="setup":
            return ["setup_music"]
        if mode=="danger":
            return ["danger_music"]
        if mode=="requiem":
            return ["requiem_music"]
        return []

    def _play_background_track(self, mode, index, fade_ms=0):
        """Play one track from the mode playlist and remember current index."""
        keys=self._music_track_keys_for_mode(mode)
        if not keys:
            return False
        valid_paths=[]
        for key in keys:
            path=self.asset_paths.get(key, "")
            if path and os.path.exists(path):
                valid_paths.append(path)
        if not valid_paths:
            return False
        idx=max(0, int(index)) % len(valid_paths)
        path=valid_paths[idx]
        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.set_volume(max(0.0, min(1.0, self.bg_music_vol.get(mode,0.42)*self.music_volume)))
            pygame.mixer.music.play(0, fade_ms=max(0, int(fade_ms)))
        except Exception:
            return False
        self.bg_music_track_index=idx
        self.bg_music_track_count=len(valid_paths)
        return True

    def _on_music_track_end(self):
        """Advance to next track in current mode playlist after a song ends."""
        mode=self.bg_music_mode
        if mode is None or self.replay_mode:
            return
        next_idx=(self.bg_music_track_index+1) % max(1, self.bg_music_track_count)
        self._play_background_track(mode, next_idx, fade_ms=0)

    def _set_background_music(self, mode, force=False):
        """Start mode playlist and switch tracks when mode changes."""
        if (not force) and mode==self.bg_music_mode:
            return
        if mode is None:
            try:
                pygame.mixer.music.stop()
            except Exception:
                pass
            self.bg_music_mode=None
            self.bg_music_track_index=0
            self.bg_music_track_count=1
            return
        try:
            if pygame.mixer.music.get_busy():
                pygame.mixer.music.fadeout(220)
            self.bg_music_mode=mode
            if not self._play_background_track(mode, 0, fade_ms=220):
                self.bg_music_mode=None
        except Exception:
            pass

    def _update_background_music(self, force=False):
        """Keep looping background music aligned with current match context."""
        self._set_background_music(self._desired_music_mode(), force=force)

    def _queue_payout_sounds(self, deltas):
        """Queue payout sound once when standings change at round end."""
        if self.replay_mode:
            return
        mag=sum(abs(_to_int(v,0)) for v in (deltas or [0,0]))
        if mag<=0:
            return
        when=max(self.tick, self.last_payout_sound_tick+280)
        self.payout_sound_ticks.append(when)
        self.last_payout_sound_tick=when

    def _tick_payout_sounds(self):
        """Play queued payout sound events at scheduled times."""
        while self.payout_sound_ticks and self.tick>=self.payout_sound_ticks[0]:
            self.payout_sound_ticks.popleft()
            self.payout_snd.play()

    def _emit_tactic_flash(self, player, tactic_name):
        """Show one short tactic-celebration banner."""
        name=(tactic_name or "").strip()
        if not name:
            return
        self.tactic_flash_text=f"{player_name(player)}: {name}"
        self.tactic_flash_until=self.tick+1000

    def _move_tactic_hits(self, game, player, kind, chosen_card, valid_cards):
        """Detect execution of high-signal defensive tactics for visual callouts."""
        hits=[]
        trump=game.trump_suit
        led=game.led_suit
        defender=(game.bid_winner in (0,1)) and (player!=game.bid_winner)
        if not defender or trump is None:
            return hits
        valid=[c for c in (valid_cards or []) if c is not None]
        if not valid:
            return hits

                                                                                   
        if game.state in (State.PLAY_HAND_FOLLOWER, State.PLAY_PILE_FOLLOWER) and game.trick_cards and led is not None:
            pot=sum(c.points() for c,_ in game.trick_cards)
            if pot>=10:
                best_pre=max((c.trick_power(led, trump) for c,_ in game.trick_cards), default=-1)
                winners=[c for c in valid if c.trick_power(led, trump)>best_pre]
                if winners and chosen_card.trick_power(led, trump)>best_pre:
                    low=min(winners, key=lambda c:c.trick_power(led, trump))
                    if chosen_card.suit==low.suit and chosen_card.rank==low.rank:
                        hits.append("Contract Breakpoint Strike")

                                                                             
        if kind=="hand" and game.state==State.PLAY_HAND_LEADER and chosen_card.suit==trump:
            if any(c.suit==trump for c in valid):
                bidder=int(game.bid_winner)
                bidder_has_trump=any(c.suit==trump for c in game.hands[bidder])
                if not bidder_has_trump:
                    bidder_has_trump=any((pile and pile[-1].suit==trump) for pile in game.piles[bidder])
                if bidder_has_trump:
                    hits.append("Trump Denial Squeeze")

                                                                                                    
        if game.state in (State.PLAY_HAND_FOLLOWER, State.PLAY_PILE_FOLLOWER) and game.trick_cards and led is not None:
            best_pre=max((c.trick_power(led, trump) for c,_ in game.trick_cards), default=-1)
            winners=[c for c in valid if c.trick_power(led, trump)>best_pre]
            if (not winners) and chosen_card.points()==0 and any(c.points()>0 for c in valid):
                hits.append("Value Leak Block")
        return hits

    def _maybe_flash_move_tactic(self, game, player, kind, chosen_card, valid_cards):
        """Emit a tactic flash if the selected move matches a named tactic."""
        if self.replay_mode:
            return
        hits=self._move_tactic_hits(game, player, kind, chosen_card, valid_cards)
        if hits:
            self._emit_tactic_flash(player, hits[0])

    def _draw_tactic_flash(self):
        """Draw active tactic celebration banner."""
        if self.tick>=self.tactic_flash_until or not self.tactic_flash_text:
            return
        R=self.R
        left_ms=max(0, self.tactic_flash_until-self.tick)
        fade=max(0.0, min(1.0, left_ms/1000.0))
        alpha=max(70, int(235*fade))
        box_w=min(920, max(420, 260+len(self.tactic_flash_text)*10))
        box_h=62
        vx=(VW-box_w)/2
        vy=20
        sr=R.r(vx, vy, box_w, box_h)
        panel=pygame.Surface((sr.w, sr.h), pygame.SRCALPHA)
        panel.fill((18, 18, 18, alpha))
        self.screen.blit(panel, sr.topleft)
        pygame.draw.rect(self.screen, (245, 210, 120), sr, max(1, R.s(2)), border_radius=max(2, R.s(10)))
        txt=R.font("bold",24).render(self.tactic_flash_text, True, (255, 238, 180))
        txt.set_alpha(alpha)
        self.screen.blit(txt, txt.get_rect(center=sr.center))

                                                                                                                                                      
    def _auto_advance(self):
                                                                                                                                                                          
        """Advance timed automatic transitions between game phases."""
        if self.replay_mode:
            return
                                                                                                                                                                       
        G=self.game; t=self.tick
                                                                                                                                                                    
        if G.state==State.TAKE_SPECIAL and t>=G.auto_timer:
                                                                                                                                                                
            G.take_special()
            self._log_farsi_flavor(
                [f"Hakem takes the special cards. Kons pressure starts now."],
                key=("take_special", self._current_game_id(), G.round_num),
                weight=0.45,
            )
                                                                                                                                                                        
            if G.bid_winner==AI_PLAYER:
                                                                                                                                                                    
                self.ai.tracker.set_hand(G.hands[AI_PLAYER])
                                                                                                                                                                    
                self._ai_discard_trump()
                                                                                                                                                      
        elif G.state==State.TRICK_RESULT and t>=G.auto_timer:

            self.ai.tracker.trick_done()

            G.next_after_trick()
            if G.state==State.ROUND_END:
                self._queue_payout_sounds(G.score_deltas)
                                                                                                                                                      
        elif G.state==State.SHELEM_CELEBRATION:
                                                                                                                                                                           
            elapsed=t-G.shelem_start
                                                                                                                                                                        
            if not self.fan_played: self.fan_snd.play(); self.fan_played=True
                                                                                                                                                                        
            if elapsed>=SHELEM_ANIM_MS:
                                                                                                                                                                                  
                G.state=State.ROUND_END; G.message=f"Round {G.round_num} Complete"
                                                                                                                                                                    
                G.sub_message=""; G.clock.pause()
                G._update_match_winner()
                                                                                                                                                                                  
                G.auto_timer=t+AUTO_ROUND_MS
                self._queue_payout_sounds(G.score_deltas)
                                                                                                                                                      
        elif G.state==State.ROUND_END and t>=G.auto_timer:
                                                                                                                                                                                                                                
            self._end_round_learn(); self.fan_played=False
                                                                                                                                                                        
            if G.match_winner is not None: self._end_match()
                                                                                                                                                       
            else: G.new_round(); self.ai.new_round(G.hands[AI_PLAYER]); self.bid_value=MIN_BID

                                                                                                                                                      
    def _ai_tick(self):
        """Trigger AI action once per turn after a small think delay."""
        if self.replay_mode:
            return
        if self.stu_ungar_active:
            return  # Stu Ungar popup owns the game state until resolved

        G=self.game

        # Stu Ungar dead-hand check: throttled to once per 600ms during hand play
        if (G.state in (State.PLAY_HAND_LEADER, State.PLAY_HAND_FOLLOWER)
                and not self.stu_ungar_active
                and G.round_num != self.stu_ungar_announced_round
                and G.trick_num >= 4
                and self.tick - self._stu_ungar_last_check_ms >= 600):
            self._stu_ungar_last_check_ms = self.tick
            dead, playback = self._is_dead_hand(G)
            if dead:
                self._trigger_stu_ungar(playback)
                return

        if G.active_player()!=AI_PLAYER: self.ai_pending=False; return
                                                                                                                                                                    
        if G.state in(State.MATCH_START,State.ROUND_END,State.TRICK_RESULT,
                                                                                                                                                                                        
                      State.MATCH_OVER,State.TAKE_SPECIAL,State.SHELEM_CELEBRATION): return
                                                                                                                                                                    
        if not self.ai_pending: self.ai_pending=True; self.ai_action_time=self.tick+AI_DELAY_MS; return
                                                                                                                                                                    
        if self.tick<self.ai_action_time: return
                                                                                                                                                                          
        self.ai_pending=False
                                                                                                                                                            
        self.ai.observe_game(G)
                                                                                                                                                            
        self.ai.tracker.update_piles(G.piles[AI_PLAYER],G.piles[HUMAN])
                                                                                                                                                                    
        if G.state==State.BIDDING: self._ai_bid()
                                                                                                                                                      
        elif G.state==State.DISCARDING: self._ai_discard_trump()
                                                                                                                                                      
        elif G.state==State.TRUMP_SELECT:
            suit=self.ai.decide_trump(G.hands[AI_PLAYER])
            G.select_trump(suit)
            self._emit_trump_flavor(AI_PLAYER, suit)
                                                                                                                                                      
        elif G.state in(State.PLAY_HAND_LEADER,State.PLAY_HAND_FOLLOWER):
                                                                                                                                                                           
            valid=G.get_valid_hand(AI_PLAYER)
                                                                                                                                                                           
            idx=self.ai.decide_play_card(G.hands[AI_PLAYER],valid,G,G.state==State.PLAY_HAND_LEADER)
            if valid and 0<=idx<len(G.hands[AI_PLAYER]):
                chosen=G.hands[AI_PLAYER][idx]
                options=[G.hands[AI_PLAYER][i] for i in valid if 0<=i<len(G.hands[AI_PLAYER])]
                self._maybe_flash_move_tactic(G, AI_PLAYER, "hand", chosen, options)
                                                                                                                                                                           
            pre_led=G.led_suit
            trump=G.trump_suit
            card=G.play_hand(AI_PLAYER,idx)
                                                                                                                                                                
            self.ai.tracker.card_played(card,AI_PLAYER); self.card_snd.play()
            self._emit_card_play_flavor(AI_PLAYER, card, pre_led, trump)
                                                                                                                                                      
        elif G.state in(State.PLAY_PILE_LEADER,State.PLAY_PILE_FOLLOWER):
                                                                                                                                                                           
            valid=G.get_valid_piles(AI_PLAYER)
                                                                                                                                                                        
            if valid:
                                                                                                                                                                               
                pi=self.ai.decide_pile_card(G.piles,valid,G,AI_PLAYER)
                if pi in valid and G.piles[AI_PLAYER][pi]:
                    chosen=G.piles[AI_PLAYER][pi][-1]
                    options=[G.piles[AI_PLAYER][i][-1] for i in valid if G.piles[AI_PLAYER][i]]
                    self._maybe_flash_move_tactic(G, AI_PLAYER, "pile", chosen, options)
                                                                                                                                                                               
                pre_led=G.led_suit
                trump=G.trump_suit
                card=G.play_pile(AI_PLAYER,pi)
                                                                                                                                                                    
                self.ai.tracker.card_played(card,AI_PLAYER); self.card_snd.play()
                self._emit_card_play_flavor(AI_PLAYER, card, pre_led, trump)

                                                                                                                                                      
    def _ai_bid(self):
                                                                                                                                                            
        """Perform AI bidding action (open bid, raise, or pass)."""
                                                                                                                                                                       
        G=self.game
                                                                                                                                                                    
        if G.last_bid[0]==0 and G.last_bid[1]==0:
                                                                                                                                                                           
            bid=self.ai.decide_bid(G.hands[AI_PLAYER])
                                                                                                                                                                        
            if bid>=MIN_BID:
                G.place_bid(bid)
                self._emit_bid_flavor(AI_PLAYER, amount=bid, passed=False)
                                                                                                                                                       
            else:
                G.pass_bid()
                self._emit_bid_flavor(AI_PLAYER, passed=True)
                                                                                                                                                   
        else:
                                                                                                                                                                           
            nb=G.current_bid+5
                                                                                                                                                                        
            if nb>MAX_BID:
                G.pass_bid()
                self._emit_bid_flavor(AI_PLAYER, passed=True)
                                                                                                                                                          
            elif self.ai.decide_should_bid(G.hands[AI_PLAYER],G.current_bid):
                G.place_bid(nb)
                self._emit_bid_flavor(AI_PLAYER, amount=nb, passed=False)
                                                                                                                                                       
            else:
                G.pass_bid()
                self._emit_bid_flavor(AI_PLAYER, passed=True)

                                                                                                                                                      
    def _ai_discard_trump(self):
                                                                                                                                                                          
        """Perform AI discard and trump selection after taking special cards."""
                                                                                                                                                                       
        G=self.game
                                                                                                                                                                    
        if G.state==State.DISCARDING:
                                                                                                                                                                
            G.discard_selected=self.ai.decide_discard(G.hands[AI_PLAYER])
                                                                                                                                                                           
            disc=G.confirm_discard()
                                                                                                                                                                        
            if disc:
                                                                                                                                                                    
                self.ai.tracker.set_discarded(disc)
                                                                                                                                                                    
                self.ai.tracker.add_virtual_trick(disc, G.bid_winner)
                self._emit_discard_flavor(AI_PLAYER, disc)
                                                                                                                                                                    
        if G.state==State.TRUMP_SELECT:
            suit=self.ai.decide_trump(G.hands[AI_PLAYER])
            G.select_trump(suit)
            self._emit_trump_flavor(AI_PLAYER, suit)
            # Build round plan now that trump and final hand are known
            self.ai.build_round_plan(
                G.hands[AI_PLAYER], suit,
                G.bid_amount, G.bid_winner==AI_PLAYER, G
            )

    def _end_round_learn(self):
        """Feed round outcome back to AI networks for online learning."""
        G=self.game
        if hasattr(G,'score_deltas'):
            ai_raw=G.round_points[AI_PLAYER] if hasattr(G,'round_points') else 0
            self.ai.learn_from_round(G.score_deltas[AI_PLAYER],G.score_deltas[HUMAN],
                                      G.bid_amount,G.bid_winner==AI_PLAYER,ai_raw)
        # Log per-round analysis to terminal
        try:
            self._log_round_analysis()
        except Exception:
            pass
                                                                                                                                                      
    def _end_match(self):
        """Finalize match history entry and enter match-over state immediately.
        Neural-network training and model persistence run in a background thread
        to avoid blocking the UI when scores reach the match target.
        """
        G=self.game; w="A" if G.match_winner==0 else "B"
        self.match_history.append({"winner":w,"score_a":G.scores[0],"score_b":G.scores[1],
                                    "rounds":G.round_num})
        # Transition to MATCH_OVER right away so the screen doesn't stall
        G.state=State.MATCH_OVER
        # Save history immediately (fast JSON write)
        self.save_history()
        # Run heavy learning + model save in a daemon thread
        ai_ref=self.ai
        ai_score=int(G.scores[AI_PLAYER]); hu_score=int(G.scores[HUMAN]); winner=G.match_winner
        def _bg_learn():
            try:
                ai_ref.learn_from_match(ai_score, hu_score, winner)
                ai_ref.save()
            except Exception:
                pass
        threading.Thread(target=_bg_learn, daemon=True).start()
                                                                                                                                                      
    def _new_match(self):
                                                                                                                                                                          
        """Create a new match using selected setup options."""
        self._start_new_match_from_setup()

    def _handle_music_mouse_down(self, sp):
        """Handle press on music volume knob/track and begin drag when hit."""
        if self.music_knob_rect and self.music_knob_rect.collidepoint(sp):
            self.music_dragging=True
            self._update_music_volume_from_screen_x(sp[0])
            return True
        if self.music_track_rect and self.music_track_rect.collidepoint(sp):
            self.music_dragging=True
            self._update_music_volume_from_screen_x(sp[0])
            return True
        return False

    def _draw_music_knob(self):
        """Draw global music volume knob/slider widget."""
        R=self.R
        vx,vy,vw,vh=VW-300,12,284,84
        sr=R.r(vx,vy,vw,vh)
        bg=pygame.Surface((sr.w,sr.h),pygame.SRCALPHA); bg.fill((0,0,0,168))
        self.screen.blit(bg,sr.topleft)
        pygame.draw.rect(self.screen,GOLD_DIM,sr,max(1,R.s(2)),border_radius=max(2,R.s(10)))
        label=R.font("bold",17).render(f"Music {int(round(self.music_volume*100))}%",True,GOLD)
        self.screen.blit(label,R.p(vx+14,vy+10))
        mode_txt=(self.bg_music_mode or "off").title()
        mt=R.font("ui_sm",12).render(mode_txt,True,(200,200,200))
        self.screen.blit(mt,R.p(vx+190,vy+14))
        tvx,tvy,tw,th=vx+16,vy+48,vw-34,10
        track=R.r(tvx,tvy,tw,th)
        self.music_track_rect=track
        pygame.draw.rect(self.screen,(58,58,58),track,border_radius=max(2,R.s(5)))
        fill_w=max(1,int(track.w*self.music_volume))
        fill=pygame.Rect(track.x,track.y,fill_w,track.h)
        pygame.draw.rect(self.screen,GOLD,fill,border_radius=max(2,R.s(5)))
        kcx=track.x+int(track.w*self.music_volume)
        kcy=track.y+track.h//2
        kr=max(6,R.s(10))
        self.music_knob_rect=pygame.Rect(kcx-kr,kcy-kr,kr*2,kr*2)
        pygame.draw.circle(self.screen,(245,245,245),(kcx,kcy),kr)
        pygame.draw.circle(self.screen,(35,35,35),(kcx,kcy),kr,max(1,R.s(2)))

                                                               
                                                                                                                                                      
    def _draw(self):
                                                                                                                                                                          
        """Render the current frame according to game/app state."""
                                                                                                                                                                       
        R=self.R; G=self.game; vm=self.vmouse; state=G.state
                                                                                                                                                            
        R.draw_felt(self.sw,self.sh)
        self._sync_game_status_to_terminal()
                                                                                                                                                                    
        if state==State.MATCH_START:
            self._draw_setup()
            self._draw_music_knob()
            self._draw_terminal()
            if self.db_inspector_open: self._draw_db_inspector()
            if self.replay_mode: self._draw_replay_hud()
            return
                                                                                                                                                                    
        if state==State.MATCH_OVER:
            self._draw_match_over()
            self._draw_music_knob()
            self._draw_terminal()
            if self.db_inspector_open: self._draw_db_inspector()
            if self.replay_mode: self._draw_replay_hud()
            return
                                                                                                                                                            
        R.draw_match_bar(G)
                                                                                                                                                            
        R.draw_text(f"\u25bc {AI_NAME}",280,16,"bold",22,AI_THINK)
                                                                                                                                                            
        R.draw_text(f"\u25b2 {HUMAN_NAME}",280,VH-82,"bold",22,(180,220,180))
                                                                                                                                                                          
        self.buttons={}
        state_code=self._state_code(G)
                                                                                                                                                            
        R.draw_text(state_code, 20,18,"bold",22,(255,235,90))
        self.buttons["grade_move"]=R.draw_button("Grade Move", 18, 52, 190, 36, vm, self._can_grade_last_move())
                                                                                                                                                            
        R.draw_turn_marker(G.active_player(),self.tick)
                                                                                                                                                             
        R.draw_trick_piles(G.trick_pile_count[1],270,75,f"Won: {G.tricks_won[1]}")
        if G.bid_winner in (HUMAN, AI_PLAYER):
            bidder=int(G.bid_winner)
            defender=1-bidder
            bid_target=max(0, _to_int(G.bid_amount, 0))
            defend_target=max(0, TOTAL_PTS-(bid_target-5))
            R.draw_contract_progress(
                150, 102,
                G.live_pts(bidder), bid_target,
                G.live_pts(defender), defend_target,
                bidder_label=player_name(bidder),
                defender_label=player_name(defender),
            )
                                                                                                                                                             
        R.draw_trick_piles(G.trick_pile_count[0],270,VH-250,f"Won: {G.tricks_won[0]}")
                                                                                                                                                            
        R.draw_chips(G.scores[HUMAN],270,VH-150,HUMAN_NAME)
                                                                                                                                                            
        R.draw_chips(G.scores[AI_PLAYER],VW-580,120,AI_NAME)
                                                                                                                                                                       
        ts=G.trump_suit
                                                                                                                                                                       
        valid_A=sel_A=None
        ai_hand_y=24
        human_hand_y=VH-BASE_CH-34
        ai_piles_y=ai_hand_y+BASE_CH+28
        human_piles_y=human_hand_y-BASE_CH-34
                                                                                                                                                                    
        if state in(State.PLAY_HAND_LEADER,State.PLAY_HAND_FOLLOWER):
                                                                                                                                                                        
            if G.active_player()==0: valid_A=set(G.get_valid_hand(0))
                                                                                                                                                                    
        if state==State.DISCARDING and G.bid_winner==0: sel_A=G.discard_selected
                                                                                                                                                                          
        self.card_rects_B=R.draw_hand(G.hands[1],ai_hand_y,hidden=not self.show_ai_hand,vmouse=vm,
                                                                                                                                                                                                     
                                      trump_suit=ts if self.show_ai_hand else None)
                                                                                                                                                                       
        vp_B=None
                                                                                                                                                                    
        if state==State.PLAY_PILE_FOLLOWER and G.trick_leader==0: vp_B=set(G.get_valid_piles(1))
                                                                                                                                                      
        elif state==State.PLAY_PILE_LEADER and G.trick_leader==1: vp_B=set(G.get_valid_piles(1))
                                                                                                                                                            
        self.pile_rects_B=R.draw_piles_row(G.piles[1],ai_piles_y,valid_indices=vp_B,vmouse=vm,trump_suit=ts)
                                                                                                                                                                       
        vp_A=None
                                                                                                                                                                    
        if state==State.PLAY_PILE_FOLLOWER and G.trick_leader==1: vp_A=set(G.get_valid_piles(0))
                                                                                                                                                      
        elif state==State.PLAY_PILE_LEADER and G.trick_leader==0: vp_A=set(G.get_valid_piles(0))
                                                                                                                                                            
        self.pile_rects_A=R.draw_piles_row(G.piles[0],human_piles_y,valid_indices=vp_A,vmouse=vm,trump_suit=ts)
                                                                                                                                                                          
        self.card_rects_A=R.draw_hand(G.hands[0],human_hand_y,valid_indices=valid_A,selected_indices=sel_A,
                                                                                                                                                                                                      
                                       vmouse=vm,trump_suit=ts)
                                                                                                                                                                    
        if G.special_pile and state==State.BIDDING:
                                                                                                                                                                           
            scx,scy=VW/2,VH/2
                                                                                                                                                                          
            for i in range(len(G.special_pile)):
                                                                                                                                                                    
                R.draw_card(G.special_pile[i],scx-BASE_CW/2+i*5,scy-BASE_CH/2-i*4,face_up=False)
                                                                                                                                                                
            R.draw_text_center("Special Pile (4)",scy+BASE_CH/2+20,"ui_sm",20,(160,160,160))
                                                                                                                                                                    
        if G.trick_cards: R.draw_trick_area(G.trick_cards,trump_suit=ts)
                                                                                                                                                                    
        if state==State.BIDDING and G.active_player()==HUMAN: self._draw_bid_ui()
                                                                                                                                                      
        elif state==State.BIDDING: pass
                                                                                                                                                      
        elif state==State.TAKE_SPECIAL: pass
                                                                                                                                                      
        elif state==State.DISCARDING and G.bid_winner==HUMAN:
                                                                                                                                                                        
            if len(G.discard_selected)==4:
                                                                                                                                                                    
                self.buttons["confirm"]=R.draw_button("Confirm Discard",VW/2-110,VH/2+35,220,48,vm)
                                                                                                                                                      
        elif state==State.TRUMP_SELECT and G.bid_winner==HUMAN: self._draw_trump_ui()
                                                                                                                                                      
        elif state in(State.PLAY_HAND_LEADER,State.PLAY_HAND_FOLLOWER,
                                                                                                                                                                                        
                      State.PLAY_PILE_LEADER,State.PLAY_PILE_FOLLOWER):
            pass
                                                                                                                                                      
        elif state==State.TRICK_RESULT: pass
                                                                                                                                                      
        elif state==State.SHELEM_CELEBRATION:
                                                                                                                                                                           
            big=G.bid_amount>=MAX_BID
                                                                                                                                                                
            R.draw_shelem(G.shelem_player,self.tick-G.shelem_start,self.tick,big)
                                                                                                                                                      
        elif state==State.ROUND_END: self._draw_round_end()
                                                                                                                                                                       
        f=R.font("ui_sm",14)
                                                                                                                                                                                                                                          
        self.screen.blit(f.render(f"{AI_NAME}: {self.ai.games_played} games | \u03b5={self.ai.epsilon:.2f}",
                                                                                                                                                                                       
                                   True,(100,100,100)),R.p(VW-380,VH-SCORE_BAR_H-20))
                                                                                                                                                            
        R.draw_score_bar(G)
        self._draw_timeline_nav_buttons()
        self._draw_tactic_flash()
        self._draw_music_knob()
        self._draw_terminal()
        if self.stu_ungar_active:
            self._draw_stu_ungar_popup()
        if self.db_inspector_open: self._draw_db_inspector()
        if self.replay_mode: self._draw_replay_hud()
        if self.tactic_grade_open: self._draw_tactic_grade_modal()

                                                                                                                                                      
    def _draw_setup(self):
                                                                                                                                                                          
        """Draw pre-game setup screen."""
                                                                                                                                                                       
        R=self.R; vm=self.vmouse; cx,cy=VW/2,VH/2
                                                                                                                                                                       
        sr=R.r(cx-540,cy-390,1080,780)
                                                                                                                                                                                                                                           
        s=pygame.Surface((sr.w,sr.h),pygame.SRCALPHA); s.fill((0,0,0,200))
                                                                                                                                                            
        self.screen.blit(s,sr.topleft)
                                                                                                                                                            
        pygame.draw.rect(self.screen,GOLD,sr,max(1,R.s(3)),border_radius=max(2,R.s(14)))
                                                                                                                                                            
        R.draw_text_center(f"\u2660 Shelem vs {AI_NAME} \u2665",cy-320,"title",56,GOLD)
                                                                                                                                                            
        R.draw_text_center(f"Clock: {self.time_minutes} min / round",cy-205,"ui",28,WHITE)
                                                                                                                                                                          
        self.buttons={}
                                                                                                                                                            
        self.buttons["td"]=R.draw_button("\u2212",cx-190,cy-155,92,62,vm,self.time_minutes>1)
                                                                                                                                                            
        self.buttons["tu"]=R.draw_button("+",cx+98,cy-155,92,62,vm,self.time_minutes<60)
                                                                                                                                                            
        R.draw_text_center(f"Match target: ${self.match_target}",cy-85,"ui",28,WHITE)
                                                                                                                                                            
        self.buttons["md"]=R.draw_button("\u2212$100",cx-260,cy-35,184,62,vm,self.match_target>200)
                                                                                                                                                            
        self.buttons["mu"]=R.draw_button("+$100",cx+76,cy-35,184,62,vm,self.match_target<5000)
                                                                                                                                                            
        self.buttons["start"]=R.draw_button("Start Match",cx-140,cy+90,280,72,vm)
                                                                                                                                                                          
        R.draw_text_center(f"{AI_NAME}: {self.ai.games_played} games | hybrid net: {self.ai.shared_net.train_steps} steps",
                                                                                                                                                                                             
                           cy+245,"ui_sm",18,AI_THINK)
        R.draw_text_center("Or use terminal commands: /load [n] /load game [g] state [s] /played",
                           cy+205,"ui_sm",18,(180,180,180))
                                                                                                                                                                    
        if self.match_history:
                                                                                                                                                                           
            wa=sum(1 for m in self.match_history if m.get('winner')=='A')
                                                                                                                                                                           
            wb=sum(1 for m in self.match_history if m.get('winner')=='B')
                                                                                                                                                                
            R.draw_text_center(f"Record: {HUMAN_NAME} {wa} \u2014 {AI_NAME} {wb}",cy+300,"bold",22,GOLD)

                                                                                                                                                      
    def _draw_match_over(self):
                                                                                                                                                                          
        """Draw match-over summary and restart controls."""
                                                                                                                                                                       
        R=self.R; G=self.game; vm=self.vmouse; cx,cy=VW/2,VH/2
                                                                                                                                                                       
        sr=R.r(cx-520,cy-330,1040,660)
                                                                                                                                                                                                                                           
        s=pygame.Surface((sr.w,sr.h),pygame.SRCALPHA); s.fill((0,0,0,210))
                                                                                                                                                            
        self.screen.blit(s,sr.topleft)
                                                                                                                                                            
        pygame.draw.rect(self.screen,GOLD,sr,max(1,R.s(3)),border_radius=max(2,R.s(14)))
        R.draw_fireworks(self.tick, cx, cy-40, radius=640, bursts=8, spark_count=20)
                                                                                                                                                                       
        w=HUMAN_NAME if G.match_winner==HUMAN else AI_NAME
                                                                                                                                                            
        R.draw_text_center(f"\U0001f3c6 {w} Wins!",cy-250,"title",56,GOLD)
                                                                                                                                                                          
        R.draw_text_center(f"Final: {HUMAN_NAME} {money_text(G.scores[HUMAN])} \u2014 {AI_NAME} {money_text(G.scores[AI_PLAYER])}",
                                                                                                                                                                                             
                           cy-145,"ui_lg",36,WHITE)
                                                                                                                                                            
        R.draw_text_center(f"{G.round_num} rounds",cy-95,"ui_sm",22,(200,200,200))
        compliments=("Spectacular finish.", "World-class table command.", "Brilliant match control.")
        mood=compliments[(self.tick//650)%len(compliments)]
        R.draw_text_center(mood,cy-35,"ui",26,(245,245,245))
                                                                                                                                                                          
        self.buttons={}
                                                                                                                                                            
        self.buttons["new"]=R.draw_button("New Match",cx-140,cy+80,280,72,vm)
                                                                                                                                                                    
        if self.match_history:
                                                                                                                                                                           
            wa=sum(1 for m in self.match_history if m.get('winner')=='A')
                                                                                                                                                                           
            wb=sum(1 for m in self.match_history if m.get('winner')=='B')
                                                                                                                                                                              
            R.draw_text_center(f"All-time: {HUMAN_NAME} {wa} \u2014 {AI_NAME} {wb}",
                                                                                                                                                                                   
                               cy+185,"bold",22,(180,180,180))

                                                                                                                                                      
    def _draw_bid_ui(self):
                                                                                                                                                                          
        """Draw human bidding controls and current bid context."""
                                                                                                                                                                       
        R=self.R; G=self.game; vm=self.vmouse; cx,cy=VW/2,VH/2
                                                                                                                                                                       
        sr=R.r(cx-420,cy-250,840,500)
                                                                                                                                                                                                                                           
        s=pygame.Surface((sr.w,sr.h),pygame.SRCALPHA); s.fill((0,0,0,180))
                                                                                                                                                            
        self.screen.blit(s,sr.topleft)
                                                                                                                                                            
        pygame.draw.rect(self.screen,GOLD_DIM,sr,max(1,R.s(2)),border_radius=max(2,R.s(14)))
                                                                                                                                                            
        R.draw_text_center(f"{HUMAN_NAME} Bid",cy-205,"ui_lg",38,GOLD)
                                                                                                                                                            
        R.draw_text_center("Use +/- and choose Bid or Pass",cy-125,"ui_sm",22,(200,200,200))
                                                                                                                                                                       
        minb=MIN_BID
                                                                                                                                                                    
        if G.last_bid[0]>0 or G.last_bid[1]>0: minb=G.current_bid+5
                                                                                                                                                            
        self.bid_value=max(self.bid_value,minb); self.bid_value=min(self.bid_value,MAX_BID)
                                                                                                                                                            
        R.draw_text_center(f"${self.bid_value}",cy-38,"title",48,WHITE)
                                                                                                                                                                       
        cl=self.bid_value-5>=minb; ch=self.bid_value+5<=MAX_BID
                                                                                                                                                            
        self.buttons["bd"]=R.draw_button("-$5",cx-295,cy+55,120,62,vm,cl)
                                                                                                                                                            
        self.buttons["bu"]=R.draw_button("+$5",cx-155,cy+55,120,62,vm,ch)
                                                                                                                                                            
        self.buttons["bb"]=R.draw_button("Bid",cx+5,cy+55,130,62,vm)
                                                                                                                                                            
        self.buttons["bp"]=R.draw_button("Pass",cx+150,cy+55,130,62,vm)
                                                                                                                                                                      
        for i in range(2):
                                                                                                                                                                           
            pn=HUMAN_NAME if i==HUMAN else AI_NAME
                                                                                                                                                                           
            st=f"{pn}: "
                                                                                                                                                                        
            if G.bid_passed[i]: st+="Passed"
                                                                                                                                                          
            elif G.last_bid[i]>0: st+=f"${G.last_bid[i]}"
                                                                                                                                                       
            else: st+="\u2014"
                                                                                                                                                                
            R.draw_text_center(st,cy+160+i*44,"ui_sm",22,(180,180,180))

                                                                                                                                                      
    def _draw_trump_ui(self):
                                                                                                                                                                          
        """Draw trump suit selection controls for the human bidder."""
                                                                                                                                                                       
        R=self.R; vm=self.vmouse; cx,cy=VW/2,VH/2
                                                                                                                                                                       
        sr=R.r(cx-420,cy-170,840,320)
                                                                                                                                                                                                                                           
        s=pygame.Surface((sr.w,sr.h),pygame.SRCALPHA); s.fill((0,0,0,180))
                                                                                                                                                            
        self.screen.blit(s,sr.topleft)
                                                                                                                                                            
        pygame.draw.rect(self.screen,GOLD_DIM,sr,max(1,R.s(2)),border_radius=max(2,R.s(14)))
                                                                                                                                                            
        R.draw_text_center("Choose Trump Suit:",cy-120,"ui",30,GOLD)
                                                                                                                                                                      
        for i,suit in enumerate(SUITS):
                                                                                                                                                                           
            bx=cx-318+i*188; by=cy-20; col=SUIT_COLOUR[suit]; bsr=R.r(bx,by,150,108)
                                                                                                                                                                           
            hover=bsr.collidepoint(*R.p(vm[0],vm[1])) if vm else False
                                                                                                                                                                           
            bg=(252,252,252) if hover else (238,238,238)
                                                                                                                                                                
            pygame.draw.rect(self.screen,bg,bsr,border_radius=max(2,R.s(10)))
                                                                                                                                                                
            pygame.draw.rect(self.screen,(90,90,90),bsr,max(1,R.s(2)),border_radius=max(2,R.s(10)))
                                                                                                                                                                           
            st=R.font("card_suit",56).render(suit,True,col)
                                                                                                                                                                
            self.screen.blit(st,st.get_rect(center=(bsr.centerx,bsr.y+R.s(40))))
                                                                                                                                                                           
            nt=R.font("ui_sm",18).render(SUIT_NAMES[suit][:3],True,(30,30,30))
                                                                                                                                                                
            self.screen.blit(nt,nt.get_rect(center=(bsr.centerx,bsr.y+R.s(88))))
                                                                                                                                                                              
            self.buttons[f"t_{suit}"]=bsr

                                                                                                                                                      
    def _draw_round_end(self):
                                                                                                                                                                          
        """Draw round-end score breakdown and match totals."""
                                                                                                                                                                       
        R=self.R; G=self.game; cx,cy=VW/2,VH/2
                                                                                                                                                                       
        sr=R.r(cx-520,cy-300,1040,600)
                                                                                                                                                                                                                                           
        s=pygame.Surface((sr.w,sr.h),pygame.SRCALPHA); s.fill((0,0,0,200))
                                                                                                                                                            
        self.screen.blit(s,sr.topleft)
                                                                                                                                                            
        pygame.draw.rect(self.screen,GOLD,sr,max(1,R.s(3)),border_radius=max(2,R.s(14)))
                                                                                                                                                            
        R.draw_text_center(f"Round {G.round_num} Results",cy-250,"title",44,GOLD)
                                                                                                                                                                      
        for i in range(2):
                                                                                                                                                                           
            pn=HUMAN_NAME if i==HUMAN else AI_NAME; pts=G.round_points[i]; delta=G.score_deltas[i]
                                                                                                                                                                           
            vc=count_value(G.cards_won[i])
                                                                                                                                                                
            R.draw_text_center(f"{pn}: {G.tricks_won[i]}tr (${G.tricks_won[i]*5}) + 5\u00d7{vc['5']} 10\u00d7{vc['10']} A\u00d7{vc['A']} = ${pts}",
                                                                                                                                                                                                 
                               cy-165+i*55,"ui_sm",20,WHITE)
                                                                                                                                                                           
            ds=f"+${delta}" if delta>=0 else f"\u2212${abs(delta)}"
                                                                                                                                                                
            R.draw_text_center(f"Score: {ds}",cy-118+i*55,"ui_sm",18,(80,255,80) if delta>=0 else (255,80,80))
                                                                                                                                                                    
        if G.bonus_msg: R.draw_text_center(G.bonus_msg,cy+28,"ui",22,GOLD)
                                                                                                                                                                          
        R.draw_text_center(f"Match \u2014 {HUMAN_NAME}: {money_text(G.scores[HUMAN])} | {AI_NAME}: {money_text(G.scores[AI_PLAYER])}",
                                                                                                                                                                                             
                           cy+108,"ui_lg",30,WHITE)
                                                                                                                                                            
        R.draw_text_center("Next round starting\u2026",cy+170,"ui_sm",18,(140,140,140))

    def _draw_terminal(self):
        """Draw always-visible slash-command terminal docked on the right side."""
        R=self.R
                                                         
                                                                                        
        music_vy,music_vh=12,84
        score_bar_h=SCORE_BAR_H
        pile_spacing=168
        pile_total_w=4*BASE_CW+3*pile_spacing
        pile_right=(VW-pile_total_w)/2+pile_total_w
        vx=min(VW-220, pile_right+24)
        vy=music_vy+music_vh+8
        vw=max(220, VW-vx)
        vh=max(220, (VH-score_bar_h)-vy)
        sr=R.r(vx,vy,vw,vh)
        self.terminal_panel_rect=sr
        bg=pygame.Surface((sr.w,sr.h),pygame.SRCALPHA); bg.fill((255,255,255,212))
        self.screen.blit(bg,sr.topleft)
        pygame.draw.rect(self.screen,(95,95,95),sr,max(1,R.s(2)),border_radius=max(2,R.s(10)))
        header=R.font("bold",22).render(f"Terminal [{self._state_code()}]",True,(95,78,36))
        self.screen.blit(header,(sr.x+R.s(10),sr.y+R.s(8)))
        f=R.font("ui_sm",18)
        line_h=30
        max_px=max(60, sr.w-R.s(26))
        wrapped=[]
        for raw in self.terminal_lines:
            ent=self._terminal_entry(raw)
            txt=ent["text"]
            col=ent["color"]
            suit_col=ent["suit_colors"]
            if not txt:
                wrapped.append({"text": "", "color": col, "suit_colors": suit_col})
                continue
            words=txt.split(" ")
            cur=""
            for w in words:
                cand=w if not cur else f"{cur} {w}"
                if f.size(cand)[0]<=max_px:
                    cur=cand
                else:
                    if cur:
                        wrapped.append({"text": cur, "color": col, "suit_colors": suit_col})
                    cur=w
            if cur:
                wrapped.append({"text": cur, "color": col, "suit_colors": suit_col})
        max_lines=max(3, int((vh-118)/line_h))
        max_scroll=max(0, len(wrapped)-max_lines)
        self.terminal_scroll_max=max_scroll
        self.terminal_scroll=max(0, min(self.terminal_scroll, max_scroll))
        start=max(0, len(wrapped)-max_lines-self.terminal_scroll)
        lines=wrapped[start:start+max_lines]
        ly=vy+56
        for ent in lines:
            self._blit_terminal_text(
                f,
                ent.get("text", ""),
                R.p(vx+10, ly)[0],
                R.p(vx+10, ly)[1],
                ent.get("color", (28,28,28)),
                suit_colors=bool(ent.get("suit_colors", True)),
            )
            ly+=line_h
        if max_scroll>0:
            rail_w=max(2, R.s(5))
            rail=pygame.Rect(sr.right-rail_w-R.s(5), sr.y+R.s(46), rail_w, max(12, sr.h-R.s(120)))
            pygame.draw.rect(self.screen,(180,180,180),rail,border_radius=max(2,R.s(3)))
            thumb_h=max(R.s(24), int(rail.h*(max_lines/max(1, len(wrapped)))))
            ratio=self.terminal_scroll/max_scroll if max_scroll>0 else 0.0
            thumb_y=rail.y+int((rail.h-thumb_h)*(1.0-ratio))
            thumb=pygame.Rect(rail.x, thumb_y, rail.w, thumb_h)
            pygame.draw.rect(self.screen,(120,120,120),thumb,border_radius=max(2,R.s(3)))
        in_vx,in_vy,in_vw,in_vh=vx+10,vy+vh-64,vw-20,50
        ir=R.r(in_vx,in_vy,in_vw,in_vh)
        self.terminal_input_rect=ir
        ibg=(250,250,250) if self.terminal_active else (242,242,242)
        pygame.draw.rect(self.screen,ibg,ir,border_radius=max(2,R.s(8)))
        pygame.draw.rect(self.screen,(120,120,120) if self.terminal_active else (160,160,160),ir,max(1,R.s(2)),
                         border_radius=max(2,R.s(8)))
        shown=self.terminal_input if self.terminal_input else ("/command" if not self.terminal_active else "")
        if self.terminal_active and (self.tick//450)%2==0:
            shown+="|"
        while shown and f.size(shown)[0]>ir.w-R.s(18):
            shown=shown[1:]
        col=(32,32,32) if self.terminal_active or self.terminal_input else (140,140,140)
        self.screen.blit(f.render(shown,True,col),R.p(in_vx+8,in_vy+8))

    def _draw_tactic_grade_modal(self):
        """Draw modal window for grading the last move transition."""
        target=self.tactic_grade_target or self._build_tactic_grade_target()
        if not target:
            self._close_tactic_grade_modal()
            return
        self.tactic_grade_target=target
        R=self.R
        dim=pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 176))
        self.screen.blit(dim, (0, 0))
        vx,vy,vw,vh=VW/2-430, VH/2-180, 860, 360
        sr=R.r(vx, vy, vw, vh)
        bg=pygame.Surface((sr.w, sr.h), pygame.SRCALPHA)
        bg.fill((14, 14, 14, 238))
        self.screen.blit(bg, sr.topleft)
        pygame.draw.rect(self.screen, GOLD, sr, max(1, R.s(3)), border_radius=max(2, R.s(12)))
        self.screen.blit(R.font("ui_lg",30).render("Grade Last Move", True, GOLD), R.p(vx+18, vy+14))
        self.screen.blit(R.font("ui_sm",16).render("Select quality label for the latest move transition.", True, (200, 200, 200)),
                         R.p(vx+18, vy+52))
        self.tactic_grade_buttons={}
        self.tactic_grade_buttons["close"]=R.draw_button("X", vx+vw-56, vy+12, 38, 34, self.vmouse, True)
        info_lines=[
            f"Game #{target.get('game_id', '?')} | States {target.get('from_state_num', '?')} -> {target.get('to_state_num', '?')} | Code {target.get('state_code', '?')}",
            f"Round {target.get('round_num', 0)}  Trick {target.get('trick_num', 0)}  State {target.get('fsm_state', '?')}",
            f"Score {HUMAN_NAME}:{target.get('score_a', 0)}  {AI_NAME}:{target.get('score_b', 0)}  "
            f"Bid ${target.get('bid_amount', 0)}  Trump {target.get('trump_suit') or '-'}",
            str(target.get("move_summary", "")),
        ]
        y=vy+94
        for line in info_lines:
            self.screen.blit(R.font("ui_sm",17).render(line, True, (232, 232, 232)), R.p(vx+22, y))
            y+=34
        grades=[("bad", "Bad"), ("neutral", "Neutral"), ("good", "Good"), ("excellent", "Excellent")]
        bw,bh=188,58
        gx=vx+22
        gy=vy+vh-86
        for i,(key,label) in enumerate(grades):
            self.tactic_grade_buttons[key]=R.draw_button(label, gx+i*(bw+14), gy, bw, bh, self.vmouse, True)

    def _draw_db_inspector(self):
        """Draw scrollable game database modal for /inspect_db."""
        R=self.R
        dim=pygame.Surface(self.screen.get_size(),pygame.SRCALPHA); dim.fill((0,0,0,170))
        self.screen.blit(dim,(0,0))
        vx,vy,vw,vh=220,120,VW-440,VH-240
        sr=R.r(vx,vy,vw,vh)
        bg=pygame.Surface((sr.w,sr.h),pygame.SRCALPHA); bg.fill((10,10,10,235))
        self.screen.blit(bg,sr.topleft)
        pygame.draw.rect(self.screen,GOLD,sr,max(1,R.s(3)),border_radius=max(2,R.s(12)))
        self.screen.blit(R.font("ui_lg",30).render("Game Database",True,GOLD),R.p(vx+18,vy+14))
        self.screen.blit(R.font("ui_sm",16).render("Click a row to open replay window. Mouse wheel to scroll.",True,(190,190,190)),
                         R.p(vx+18,vy+48))
        self.db_close_rect=R.r(vx+vw-48,vy+10,36,30)
        pygame.draw.rect(self.screen,(80,30,30),self.db_close_rect,border_radius=max(2,R.s(6)))
        pygame.draw.rect(self.screen,GOLD_DIM,self.db_close_rect,max(1,R.s(2)),border_radius=max(2,R.s(6)))
        self.screen.blit(R.font("bold",20).render("X",True,WHITE),
                         R.font("bold",20).render("X",True,WHITE).get_rect(center=self.db_close_rect.center))
        row_h=96
        vis=max(1, int((vh-106)/row_h))
        start=max(0, min(self.db_inspector_scroll, max(0, len(self.db_inspector_items)-vis)))
        self.db_inspector_scroll=start
        self.db_row_rects=[]
        for i in range(vis):
            idx=start+i
            if idx>=len(self.db_inspector_items):
                break
            item=self.db_inspector_items[idx]
            rvx,rvy= vx+16, vy+78+i*row_h
            rr=R.r(rvx,rvy,vw-32,row_h-8)
            hover=rr.collidepoint(*R.p(self.vmouse[0],self.vmouse[1]))
            pygame.draw.rect(self.screen,(52,52,52) if hover else (34,34,34),rr,border_radius=max(2,R.s(6)))
            pygame.draw.rect(self.screen,GOLD_DIM,rr,max(1,R.s(1)),border_radius=max(2,R.s(6)))
            gid=_to_int(item.get("id", 0), 0)
            states=_to_int(item.get("states_count", 0), 0)
            moves=_to_int(item.get("moves_count", 0), 0)
            winner=item.get("winner", None)
            if winner in (0,1):
                wn=HUMAN_NAME if int(winner)==0 else AI_NAME
            else:
                wn="In Progress"
            sa=_to_int(item.get("final_score_a", 0), 0)
            sb=_to_int(item.get("final_score_b", 0), 0)
            r1=f"#{gid}  Winner: {wn}  States: {states}  Moves: {moves}"
            r2=f"Score {HUMAN_NAME}:{sa}  {AI_NAME}:{sb}  Round:{_to_int(item.get('latest_round_num',0),0)}  State:{item.get('latest_fsm_state') or '-'}"
            self.screen.blit(R.font("bold",18).render(r1,True,WHITE),R.p(rvx+10,rvy+8))
            self.screen.blit(R.font("ui_sm",15).render(r2,True,(190,190,190)),R.p(rvx+10,rvy+34))
            self.db_row_rects.append((rr, gid, _to_int(item.get("latest_state_num", 1), 1)))

    def _draw_replay_hud(self):
        """Draw replay navigation hint while in separate replay window."""
        if not self.replay_mode:
            return
        R=self.R
        total=len(self.replay_states)
        if total<=0:
            return
        sn=self.replay_states[self.replay_index][0]
        txt=f"Replay Game #{self.replay_game_id}  State {sn}/{total}  Code {self._state_code()}  (\u2190/\u2192 navigate)"
        R.draw_text_center(txt,28,"ui_sm",18,GOLD)

    def _draw_timeline_nav_buttons(self):
        """Draw in-game timeline navigation controls."""
        if self.replay_mode or self.timeline_game_id is None:
            return
        R=self.R
        vm=self.vmouse
        vx=14
        vy=VH-SCORE_BAR_H-48
        bw,bh=58,42
        gap=8
        can_back=self.timeline_state_num>1
        can_fwd=False
        can_live=False
        if self.timeline_nav_active:
            can_back=self.timeline_nav_index>0
            can_fwd=self.timeline_nav_index<self.timeline_nav_live_index
            can_live=self.timeline_nav_index<self.timeline_nav_live_index
        self.buttons["timeline_back"]=R.draw_button("←", vx, vy, bw, bh, vm, can_back)
        self.buttons["timeline_fwd"]=R.draw_button("→", vx+bw+gap, vy, bw, bh, vm, can_fwd)
        self.buttons["timeline_live"]=R.draw_button("▶", vx+(bw+gap)*2, vy, bw, bh, vm, can_live)
        if self.timeline_nav_active:
            snap=None
            if 0<=self.timeline_nav_index<len(self.timeline_nav_states):
                snap=self.timeline_nav_states[self.timeline_nav_index][1]
            g=(snap or {}).get("game") or {}
            rr=_to_int(g.get("round_num", 0), 0)
            tt=_to_int(g.get("trick_num", 0), 0)
            status=f"History R{rr:02d} T{tt:02d}  ({self.timeline_nav_index+1}/{self.timeline_nav_live_index+1})"
            col=(255,225,140)
        else:
            status="Live"
            col=(210,210,210)
        R.draw_text(status, vx+(bw+gap)*3+14, vy+12, "ui_sm", 16, col)

    def _blit_terminal_text(self, font, text, x, y, base_color, suit_colors=True):
        """Render terminal line with optional per-suit glyph coloring."""
        cx=x
        chunk=""
        def _flush(seg, col):
            nonlocal cx
            if not seg:
                return
            surf=font.render(seg, True, col)
            self.screen.blit(surf, (cx, y))
            cx+=surf.get_width()
        for ch in str(text):
            if suit_colors and ch in SUITS:
                _flush(chunk, base_color)
                chunk=""
                _flush(ch, SUIT_COLOUR.get(ch, base_color))
            else:
                chunk+=ch
        _flush(chunk, base_color)

                                                               
                                                                                                                                                      
    def _handle_click(self,sp):
                                                                                                                                                                          
        """Route click events to the active state's interaction handler."""
                                                                                                                                                                       
        G=self.game; state=G.state
        if self.tactic_grade_open:
            for key,rr in (self.tactic_grade_buttons or {}).items():
                if rr and rr.collidepoint(sp):
                    if key=="close":
                        self._close_tactic_grade_modal()
                    else:
                        self._save_tactic_grade(key)
                    return
            self._close_tactic_grade_modal()
            return
                                          
        if (self.terminal_input_rect and self.terminal_input_rect.collidepoint(sp)) or\
           (self.terminal_panel_rect and self.terminal_panel_rect.collidepoint(sp)):
            self._activate_terminal()
            return
                                                      
        if self.db_inspector_open:
            if self.db_close_rect and self.db_close_rect.collidepoint(sp):
                self.db_inspector_open=False
                return
            for rr,gid,latest_state in self.db_row_rects:
                if rr.collidepoint(sp):
                    self._launch_replay_window(gid, max(1, latest_state))
                    return
            return
        if not self.replay_mode:
            if "grade_move" in self.buttons and self.buttons["grade_move"].collidepoint(sp):
                self._open_tactic_grade_modal()
                return
            if "timeline_back" in self.buttons and self.buttons["timeline_back"].collidepoint(sp):
                self._timeline_nav_step(-1)
                return
            if "timeline_fwd" in self.buttons and self.buttons["timeline_fwd"].collidepoint(sp):
                self._timeline_nav_step(+1)
                return
            if "timeline_live" in self.buttons and self.buttons["timeline_live"].collidepoint(sp):
                self._timeline_nav_jump_live()
                return
            if self.timeline_nav_active:
                return
                                                                                                                                                                      
        for rect,_ in getattr(self,"card_rects_B",[]):
                                                                                                                                                                        
            if rect.collidepoint(sp):
                                                                                                                                                                                  
                self.show_ai_hand=not self.show_ai_hand
                                                                                                                                                          
                return
                                                                                
        if self.replay_mode:
            return
                                                                                                                                                                    
        if state==State.MATCH_START: self._setup_click(sp); return
                                                                                                                                                                    
        if state==State.MATCH_OVER:
                                                                                                                                                                        
            if "new" in self.buttons and self.buttons["new"].collidepoint(sp): self._new_match()
                                                                                                                                                      
            return
                                                                                                                                                                    
        if state==State.BIDDING and G.active_player()==HUMAN: self._bid_click(sp)
                                                                                                                                                      
        elif state==State.DISCARDING and G.bid_winner==HUMAN: self._disc_click(sp)
                                                                                                                                                      
        elif state==State.TRUMP_SELECT and G.bid_winner==HUMAN:
                                                                                                                                                                          
            for suit in SUITS:
                                                                                                                                                                               
                k=f"t_{suit}"
                                                                                                                                                                            
                if k in self.buttons and self.buttons[k].collidepoint(sp):
                    G.select_trump(suit)
                    self._emit_trump_flavor(HUMAN, suit)
                    break
                                                                                                                                                      
        elif state in(State.PLAY_HAND_LEADER,State.PLAY_HAND_FOLLOWER) and G.active_player()==HUMAN:
                                                                                                                                                                
            self._hand_click(sp,HUMAN)
                                                                                                                                                      
        elif state in(State.PLAY_PILE_LEADER,State.PLAY_PILE_FOLLOWER) and G.active_player()==HUMAN:
                                                                                                                                                                
            self._pile_click(sp,HUMAN)

                                                                                                                                                      
    def _setup_click(self,sp):
                                                                                                                                                                          
        """Handle click interactions on setup screen controls."""
                                                                                                                                                                       
        b=self.buttons
                                                                                                                                                                    
        if "td" in b and b["td"].collidepoint(sp): self.time_minutes=max(1,self.time_minutes-1)
                                                                                                                                                      
        elif "tu" in b and b["tu"].collidepoint(sp): self.time_minutes=min(60,self.time_minutes+1)
                                                                                                                                                      
        elif "md" in b and b["md"].collidepoint(sp): self.match_target=max(200,self.match_target-100)
                                                                                                                                                      
        elif "mu" in b and b["mu"].collidepoint(sp): self.match_target=min(5000,self.match_target+100)
                                                                                                                                                      
        elif "start" in b and b["start"].collidepoint(sp):
            self._start_new_match_from_setup()
                                                                                                                                                      
    def _setup_key(self,event):
                                                                                                                                                                          
        """Handle setup keyboard shortcuts."""
                                                                                                                                                                    
        if event.key==pygame.K_RETURN:
            self._start_new_match_from_setup()
                                                                                                                                                      
        elif event.key in(pygame.K_UP,pygame.K_RIGHT): self.time_minutes=min(60,self.time_minutes+1)
                                                                                                                                                      
        elif event.key in(pygame.K_DOWN,pygame.K_LEFT): self.time_minutes=max(1,self.time_minutes-1)

                                                                                                                                                      
    def _bid_click(self,sp):
                                                                                                                                                                          
        """Handle click interactions in the bidding panel."""
                                                                                                                                                                       
        G=self.game; minb=MIN_BID
                                                                                                                                                                    
        if G.last_bid[0]>0 or G.last_bid[1]>0: minb=G.current_bid+5
                                                                                                                                                                       
        b=self.buttons
                                                                                                                                                                    
        if "bd" in b and b["bd"].collidepoint(sp):
                                                                                                                                                                        
            if self.bid_value-5>=minb: self.bid_value-=5
                                                                                                                                                      
        elif "bu" in b and b["bu"].collidepoint(sp):
                                                                                                                                                                        
            if self.bid_value+5<=MAX_BID: self.bid_value+=5
                                                                                                                                                      
        elif "bb" in b and b["bb"].collidepoint(sp):
                                                                                                                                                                
            placed=self.bid_value
            G.place_bid(placed); self.bid_value=min(self.bid_value+5,MAX_BID)
            self._emit_bid_flavor(HUMAN, amount=placed, passed=False)
                                                                                                                                                      
        elif "bp" in b and b["bp"].collidepoint(sp):
            G.pass_bid()
            self._emit_bid_flavor(HUMAN, passed=True)

                                                                                                                                                      
    def _disc_click(self,sp):
                                                                                                                                                                          
        """Handle click interactions in discard-selection UI."""
                                                                                                                                                                       
        G=self.game
                                                                                                                                                                    
        if "confirm" in self.buttons and self.buttons["confirm"].collidepoint(sp):
                                                                                                                                                                           
            disc=G.confirm_discard()
                                                                                                                                                                        
            if disc and G.bid_winner==AI_PLAYER:
                self.ai.tracker.set_discarded(disc)
                                                                                                                                                                    
                self.ai.tracker.add_virtual_trick(disc, G.bid_winner)
            if disc:
                self._emit_discard_flavor(HUMAN, disc)
                                                                                                                                                      
            return
                                                                                                                                                                      
        for rect,idx in reversed(self.card_rects_A):
                                                                                                                                                                        
            if rect.collidepoint(sp): G.toggle_discard(idx); break

                                                                                                                                                      
    def _hand_click(self,sp,player):
                                                                                                                                                                          
        """Handle click-to-play from a hand row for `player`."""
                                                                                                                                                                       
        G=self.game; valid=set(G.get_valid_hand(player))
                                                                                                                                                                      
        for rect,idx in reversed(self.card_rects_A):
                                                                                                                                                                        
            if rect.collidepoint(sp) and idx in valid:
                self._maybe_flash_move_tactic(
                    G,
                    player,
                    "hand",
                    G.hands[player][idx],
                    [G.hands[player][i] for i in valid if 0<=i<len(G.hands[player])],
                )
                                                                                                                                                                               
                pre_led=G.led_suit
                trump=G.trump_suit
                card=G.play_hand(player,idx)
                                                                                                                                                                    
                self.ai.tracker.card_played(card,player); self.card_snd.play()
                self._emit_card_play_flavor(player, card, pre_led, trump)
                break

                                                                                                                                                      
    def _pile_click(self,sp,player):
                                                                                                                                                                          
        """Handle click-to-play from pile tops for `player`."""
                                                                                                                                                                       
        G=self.game; valid=set(G.get_valid_piles(player))
                                                                                                                                                                      
        for rect,pi in self.pile_rects_A:
                                                                                                                                                                        
            if rect.collidepoint(sp) and pi in valid:
                if G.piles[player][pi]:
                    self._maybe_flash_move_tactic(
                        G,
                        player,
                        "pile",
                        G.piles[player][pi][-1],
                        [G.piles[player][i][-1] for i in valid if G.piles[player][i]],
                    )
                                                                                                                                                                               
                pre_led=G.led_suit
                trump=G.trump_suit
                card=G.play_pile(player,pi)
                                                                                                                                                                    
                self.ai.tracker.card_played(card,player); self.card_snd.play()
                self._emit_card_play_flavor(player, card, pre_led, trump)
                break

                                                                                                                                                            
def _parse_cli(argv):
    """Parse replay and headless self-play command-line options."""
    replay_game_id=None
    replay_state_num=1
    self_play_matches=0
    target_amount=1000
    i=1
    while i<len(argv):
        a=argv[i]
        if a=="--replay-game" and i+1<len(argv):
            replay_game_id=_to_int(argv[i+1], -1)
            i+=2
            continue
        if a=="--replay-state" and i+1<len(argv):
            replay_state_num=max(1, _to_int(argv[i+1], 1))
            i+=2
            continue
        if a=="--self-play" and i+1<len(argv):
            self_play_matches=max(0, _to_int(argv[i+1], 0))
            i+=2
            continue
        if a=="--target-amount" and i+1<len(argv):
            target_amount=max(100, _to_int(argv[i+1], 1000))
            i+=2
            continue
        i+=1
    if replay_game_id is not None and replay_game_id<=0:
        replay_game_id=None
    return replay_game_id, replay_state_num, self_play_matches, target_amount


def _mirror_player_idx(p):
    if p is None:
        return None
    return 1-int(p)


def _mirror_game_state(game):
    """Return a deep-copied player-swapped view so AI_PLAYER always means side-to-train."""
    g=copy.deepcopy(game)
    g.hands=[copy.deepcopy(game.hands[1]), copy.deepcopy(game.hands[0])]
    g.piles=[copy.deepcopy(game.piles[1]), copy.deepcopy(game.piles[0])]
    g.tricks_won=[int(game.tricks_won[1]), int(game.tricks_won[0])]
    g.cards_won=[copy.deepcopy(game.cards_won[1]), copy.deepcopy(game.cards_won[0])]
    g.trick_pile_count=[int(game.trick_pile_count[1]), int(game.trick_pile_count[0])]
    g.scores=[int(game.scores[1]), int(game.scores[0])]
    g.score_deltas=[int(game.score_deltas[1]), int(game.score_deltas[0])]
    g.round_points=[int(game.round_points[1]), int(game.round_points[0])]
    g.bid_passed=[bool(game.bid_passed[1]), bool(game.bid_passed[0])]
    g.last_bid=[int(game.last_bid[1]), int(game.last_bid[0])]
    g.trick_cards=[(c.copy(), _mirror_player_idx(p)) for c,p in game.trick_cards]
    g.bid_winner=_mirror_player_idx(game.bid_winner)
    g.bidder_turn=_mirror_player_idx(game.bidder_turn)
    g.trick_leader=_mirror_player_idx(game.trick_leader)
    g.first_dealer=_mirror_player_idx(game.first_dealer)
    g.match_winner=_mirror_player_idx(game.match_winner)
    g.shelem_player=_mirror_player_idx(game.shelem_player)
    g.clock=copy.deepcopy(game.clock)
    g.clock.rem=[float(game.clock.rem[1]), float(game.clock.rem[0])]
    g.clock.initial=[float(game.clock.initial[1]), float(game.clock.initial[0])]
    g.clock.flagged=[bool(game.clock.flagged[1]), bool(game.clock.flagged[0])]
    g.clock.active=_mirror_player_idx(game.clock.active)
    return g


class _HeadlessSeat:
    """Adapter exposing any real player as AI_PLAYER perspective for one ShelemAI instance."""
    def __init__(self, ai, real_self_player):
        self.ai=ai
        self.real_self_player=int(real_self_player)
    def _view(self, game):
        if self.real_self_player==AI_PLAYER:
            return game
        return _mirror_game_state(game)
    def begin_round(self, game):
        vg=self._view(game)
        self.ai.new_round(vg.hands[AI_PLAYER])
        self.ai.observe_game(vg)
    def decide_bid_open(self, game):
        vg=self._view(game)
        self.ai.observe_game(vg)
        return self.ai.decide_bid(vg.hands[AI_PLAYER])
    def decide_should_bid(self, game, cur):
        vg=self._view(game)
        self.ai.observe_game(vg)
        return self.ai.decide_should_bid(vg.hands[AI_PLAYER], cur)
    def decide_discard(self, game):
        vg=self._view(game)
        self.ai.observe_game(vg)
        return self.ai.decide_discard(vg.hands[AI_PLAYER])
    def decide_trump(self, game):
        vg=self._view(game)
        self.ai.observe_game(vg)
        return self.ai.decide_trump(vg.hands[AI_PLAYER])
    def decide_hand_idx(self, game):
        vg=self._view(game)
        self.ai.observe_game(vg)
        valid=vg.get_valid_hand(AI_PLAYER)
        is_leading=vg.state==State.PLAY_HAND_LEADER
        return self.ai.decide_play_card(vg.hands[AI_PLAYER], valid, vg, is_leading)
    def decide_pile_idx(self, game):
        vg=self._view(game)
        self.ai.observe_game(vg)
        valid=vg.get_valid_piles(AI_PLAYER)
        return self.ai.decide_pile_card(vg.piles, valid, vg, AI_PLAYER)
    def on_card_played(self, card, real_player):
        persp=AI_PLAYER if int(real_player)==self.real_self_player else HUMAN
        self.ai.tracker.card_played(card, persp)
    def on_trick_done(self):
        self.ai.tracker.trick_done()
    def on_discard(self, disc, real_bid_winner):
        if int(real_bid_winner)==self.real_self_player and disc:
            self.ai.tracker.set_discarded(disc)
            self.ai.tracker.add_virtual_trick(disc, AI_PLAYER)
    def learn_round(self, game):
        was_bidder=(int(game.bid_winner)==self.real_self_player)
        ai_delta=game.score_deltas[self.real_self_player]
        opp_delta=game.score_deltas[1-self.real_self_player]
        ai_raw=game.round_points[self.real_self_player]
        self.ai.learn_from_round(ai_delta, opp_delta, game.bid_amount, was_bidder, ai_raw)
    def learn_match(self, game):
        ai_score=game.scores[self.real_self_player]
        opp_score=game.scores[1-self.real_self_player]
        if game.match_winner is None:
            winner=None
        elif int(game.match_winner)==self.real_self_player:
            winner=AI_PLAYER
        else:
            winner=HUMAN
        self.ai.learn_from_match(ai_score, opp_score, winner)


def _clone_shared_net(src_ai, dst_ai):
    """Copy shared model weights and counters from source AI into destination AI."""
    dst_ai.shared_net=copy.deepcopy(src_ai.shared_net)
    dst_ai.epsilon=src_ai.epsilon
    dst_ai.games_played=src_ai.games_played


def _self_play_value_target(ai_score, opp_score, winner):
    """Mirror match-end value target shaping used by `ShelemAI.learn_from_match`."""
    scale=max(1.0, float(abs(ai_score)+abs(opp_score)))
    value_target=float(np.clip((ai_score-opp_score)/scale, -1.0, 1.0))
    if winner==AI_PLAYER:
        value_target=max(value_target, 0.2)
    elif winner==HUMAN:
        value_target=min(value_target, -0.2)
    return value_target


def _count_match_examples(examples):
    """Return per-head trajectory counts for queued match examples."""
    counts={"bid":0, "hand":0, "pile":0}
    for _,head,_ in examples:
        key=str(head)
        if key in counts:
            counts[key]+=1
    return counts


def _run_headless_self_play(n_matches, target_amount):
    """Run headless self-play training session and persist shared model."""
    global MC_SAMPLES, BG_TREE_DEPTH
    n=max(1, int(n_matches))
    target=max(100, int(target_amount))
    print(f"[self-play] matches={n} target=${target}", flush=True)
    learner=ShelemAI()
    opponent=ShelemAI()
    orig_mc_samples=MC_SAMPLES
    orig_bg_depth=BG_TREE_DEPTH
    try:
                                                                                   
        MC_SAMPLES=max(12, min(32, orig_mc_samples//2 if orig_mc_samples>0 else 20))
        BG_TREE_DEPTH=max(1, min(2, orig_bg_depth))
        print(
            f"[self-play] runtime_tuning MC_SAMPLES={orig_mc_samples}->{MC_SAMPLES} "
            f"BG_TREE_DEPTH={orig_bg_depth}->{BG_TREE_DEPTH}",
            flush=True,
        )
        print(
            f"[self-play] learner_init epsilon={learner.epsilon:.4f} "
            f"train_steps={learner.shared_net.train_steps} games={learner.games_played} "
            f"shared_lr={SHARED_NET_LR:.6f} "
            f"arch=belief6/policy12",
            flush=True,
        )
        _clone_shared_net(learner, opponent)
        total_wins=0
        total_losses=0
        total_draws=0
        total_score_diff=0
        total_rounds=0
        for mi in range(1, n+1):
            learner_side=1 if (mi%2==1) else 0
            game=ShelemGame(match_target=target)
            game.new_round()
            game.clock.initial=[8.0, 8.0]
            game.clock.rem=[8.0, 8.0]
            if learner_side==1:
                seat0=_HeadlessSeat(opponent, 0)
                seat1=_HeadlessSeat(learner, 1)
            else:
                seat0=_HeadlessSeat(learner, 0)
                seat1=_HeadlessSeat(opponent, 1)
            seats={0:seat0, 1:seat1}
            seat0.begin_round(game)
            seat1.begin_round(game)
            steps=0
            max_steps=max(2400, target*16)
            forced_outcome=False
            rounds_played=0
            learner_round_wins=0
            opp_round_wins=0
            learner_bid_rounds=0
            opp_bid_rounds=0
            learner_contracts_made=0
            opp_contracts_made=0
            learner_shelem_rounds=0
            opp_shelem_rounds=0
            def _capture_round_stats():
                nonlocal rounds_played
                nonlocal learner_round_wins, opp_round_wins
                nonlocal learner_bid_rounds, opp_bid_rounds
                nonlocal learner_contracts_made, opp_contracts_made
                nonlocal learner_shelem_rounds, opp_shelem_rounds
                rounds_played+=1
                bidder=game.bid_winner
                if bidder is not None:
                    bidder=int(bidder)
                    bidder_made=game.round_points[bidder]>=game.bid_amount
                    if bidder==learner_side:
                        learner_bid_rounds+=1
                        if bidder_made:
                            learner_contracts_made+=1
                    elif bidder==(1-learner_side):
                        opp_bid_rounds+=1
                        if bidder_made:
                            opp_contracts_made+=1
                ldelta=int(game.score_deltas[learner_side])
                odelta=int(game.score_deltas[1-learner_side])
                if ldelta>odelta:
                    learner_round_wins+=1
                elif odelta>ldelta:
                    opp_round_wins+=1
                if game.shelem_player is not None:
                    sp=int(game.shelem_player)
                    if sp==learner_side:
                        learner_shelem_rounds+=1
                    elif sp==(1-learner_side):
                        opp_shelem_rounds+=1
            while game.match_winner is None:
                steps+=1
                if steps>max_steps:
                                                                                       
                    forced_outcome=True
                    if game.scores[0]==game.scores[1]:
                        game.match_winner=learner_side
                    else:
                        game.match_winner=0 if game.scores[0]>game.scores[1] else 1
                    break
                s=game.state
                if s==State.BIDDING:
                    p=int(game.bidder_turn)
                    seat=seats[p]
                    if game.last_bid[0]==0 and game.last_bid[1]==0:
                        bid=seat.decide_bid_open(game)
                        if bid>=MIN_BID:
                            game.place_bid(bid)
                        else:
                            game.pass_bid()
                    else:
                        nb=game.current_bid+5
                        if nb>MAX_BID:
                            game.pass_bid()
                        elif seat.decide_should_bid(game, game.current_bid):
                            game.place_bid(nb)
                        else:
                            game.pass_bid()
                    continue
                if s==State.TAKE_SPECIAL:
                    game.take_special()
                    continue
                if s==State.DISCARDING:
                    p=int(game.bid_winner)
                    seat=seats[p]
                    game.discard_selected=seat.decide_discard(game)
                    disc=game.confirm_discard()
                    if disc:
                        seat0.on_discard(disc, p)
                        seat1.on_discard(disc, p)
                    continue
                if s==State.TRUMP_SELECT:
                    p=int(game.bid_winner)
                    suit=seats[p].decide_trump(game)
                    game.select_trump(suit)
                    continue
                if s in (State.PLAY_HAND_LEADER, State.PLAY_HAND_FOLLOWER):
                    p=int(game.active_player())
                    idx=seats[p].decide_hand_idx(game)
                    card=game.play_hand(p, idx)
                    seat0.on_card_played(card, p)
                    seat1.on_card_played(card, p)
                    continue
                if s in (State.PLAY_PILE_LEADER, State.PLAY_PILE_FOLLOWER):
                    p=int(game.active_player())
                    valid=game.get_valid_piles(p)
                    if valid:
                        pi=seats[p].decide_pile_idx(game)
                        if pi not in valid:
                            pi=valid[0]
                        card=game.play_pile(p, pi)
                        seat0.on_card_played(card, p)
                        seat1.on_card_played(card, p)
                    else:
                        game._resolve_trick()
                    continue
                if s==State.TRICK_RESULT:
                    seat0.on_trick_done()
                    seat1.on_trick_done()
                    game.next_after_trick()
                    continue
                if s==State.SHELEM_CELEBRATION:
                    game.state=State.ROUND_END
                    game.clock.pause()
                    game._update_match_winner()
                    continue
                if s==State.ROUND_END:
                    _capture_round_stats()
                    seat0.learn_round(game)
                    seat1.learn_round(game)
                    if game.match_winner is None:
                        game.new_round()
                        game.clock.initial=[8.0, 8.0]
                        game.clock.rem=[8.0, 8.0]
                        seat0.begin_round(game)
                        seat1.begin_round(game)
                    continue
                if s in (State.MATCH_START, State.MATCH_OVER):
                    break
                raise RuntimeError(f"Unhandled self-play state: {s}")
            if game.state==State.ROUND_END and rounds_played<game.round_num:
                _capture_round_stats()

            lscore=game.scores[learner_side]
            oscore=game.scores[1-learner_side]
            if game.match_winner is None:
                learner_winner=None
            elif int(game.match_winner)==learner_side:
                learner_winner=AI_PLAYER
            else:
                learner_winner=HUMAN
            samples_queued=len(learner.match_examples)
            sample_counts=_count_match_examples(learner.match_examples)
            eps_before=float(learner.epsilon)
            train_steps_before=int(learner.shared_net.train_steps)
            value_target=_self_play_value_target(lscore, oscore, learner_winner)
            if learner_side==1:
                seat1.learn_match(game)
            else:
                seat0.learn_match(game)
            eps_after=float(learner.epsilon)
            train_steps_after=int(learner.shared_net.train_steps)
            trained_steps=max(0, train_steps_after-train_steps_before)
            is_capped=samples_queued>2048
            win=learner_winner==AI_PLAYER
            lose=learner_winner==HUMAN
            if win:
                total_wins+=1
            elif lose:
                total_losses+=1
            else:
                total_draws+=1
            score_diff=int(lscore-oscore)
            total_score_diff+=score_diff
            total_rounds+=rounds_played
            winner_label="learner" if win else ("opponent" if lose else "none")
            forced_note=" forced=max_steps" if forced_outcome else ""
            capped_note=" capped=2048" if is_capped else ""
            print(
                f"[self-play] match {mi}/{n} side={learner_side} winner={winner_label} "
                f"score(L/O)={lscore}/{oscore} diff={score_diff:+d} rounds={rounds_played} "
                f"round_wins(L/O)={learner_round_wins}/{opp_round_wins} "
                f"contracts_made(L/O)={learner_contracts_made}/{learner_bid_rounds}"
                f"|{opp_contracts_made}/{opp_bid_rounds} "
                f"shelem(L/O)={learner_shelem_rounds}/{opp_shelem_rounds} "
                f"sim_steps={steps}{forced_note}",
                flush=True,
            )
            print(
                f"[self-play] match {mi}/{n} tuning "
                f"value_target={value_target:+.3f} samples={samples_queued}{capped_note} "
                f"(bid={sample_counts['bid']} hand={sample_counts['hand']} pile={sample_counts['pile']}) "
                f"train_steps={train_steps_before}->{train_steps_after} (+{trained_steps}) "
                f"epsilon={eps_before:.4f}->{eps_after:.4f}",
                flush=True,
            )
            if mi%4==0:
                _clone_shared_net(learner, opponent)
                print(
                    f"[self-play] sync opponent @match={mi} train_steps={learner.shared_net.train_steps}",
                    flush=True,
                )
            if mi%5==0 or mi==n:
                learner.save()
                print(
                    f"[self-play] checkpoint saved @match={mi} train_steps={learner.shared_net.train_steps}",
                    flush=True,
                )
        learner.save()
        avg_score_diff=total_score_diff/max(1, n)
        avg_rounds=total_rounds/max(1, n)
        print(
            f"[self-play] done wins={total_wins} losses={total_losses} draws={total_draws} "
            f"avg_diff={avg_score_diff:+.1f} avg_rounds={avg_rounds:.2f} "
            f"final_epsilon={learner.epsilon:.4f} final_train_steps={learner.shared_net.train_steps}",
            flush=True,
        )
    finally:
        MC_SAMPLES=orig_mc_samples
        BG_TREE_DEPTH=orig_bg_depth
        learner.shutdown()
        opponent.shutdown()

if __name__=="__main__":
    _apply_process_memory_limit(PROCESS_MEMORY_CAP_MB)
    _memory_pressure(force=True)
                                                                                                                                                                   
    replay_gid,replay_sid,self_play_n,target_amount=_parse_cli(sys.argv)
    if self_play_n>0:
        _run_headless_self_play(self_play_n, target_amount)
    else:
        app=ShelemApp(replay_game_id=replay_gid, replay_state_num=replay_sid); app.run()
