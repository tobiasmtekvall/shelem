"""Hybrid Jarvis AI components.

This module provides:
1) Pluggable tactic registry (named heuristics).
2) Belief transformer for hidden-card inference.
3) Policy/value transformer for action priors and evaluation.
4) Utility weighted sampling for information-set Monte Carlo.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import os
import random
from typing import Callable

import numpy as np


def _softmax_1d(x: np.ndarray) -> np.ndarray:
    x=np.asarray(x, dtype=np.float32).reshape(-1)
    if x.size==0:
        return x
    z=x-np.max(x)
    ez=np.exp(z, dtype=np.float32)
    den=float(np.sum(ez, dtype=np.float32))+1e-9
    return ez/den


def _softmax_rows(x: np.ndarray) -> np.ndarray:
    x=np.asarray(x, dtype=np.float32)
    if x.ndim==1:
        x=x.reshape(1, -1)
    z=x-np.max(x, axis=1, keepdims=True)
    ez=np.exp(z, dtype=np.float32)
    den=np.sum(ez, axis=1, keepdims=True, dtype=np.float32)+1e-9
    return ez/den


def _layer_norm(x: np.ndarray, eps: float = 1e-5) -> np.ndarray:
    mu=np.mean(x, axis=-1, keepdims=True, dtype=np.float32)
    var=np.mean((x-mu)*(x-mu), axis=-1, keepdims=True, dtype=np.float32)
    return (x-mu)/np.sqrt(var+eps, dtype=np.float32)


def _relu(x: np.ndarray) -> np.ndarray:
    return np.maximum(x, 0.0, dtype=np.float32)


def weighted_sample_without_replacement(
    items: list[int], weights: list[float] | np.ndarray, k: int
) -> list[int]:
    """Weighted sampling without replacement with graceful fallback."""
    if k<=0 or not items:
        return []
    k=min(int(k), len(items))
    pool=list(items)
    w=np.asarray(weights, dtype=np.float64).reshape(-1)
    if w.size!=len(pool):
        w=np.ones(len(pool), dtype=np.float64)
    w=np.maximum(w, 0.0)
    out=[]
    for _ in range(k):
        if not pool:
            break
        total=float(np.sum(w))
        if total<=1e-12:
            idx=random.randrange(len(pool))
        else:
            r=random.random()*total
            c=0.0
            idx=0
            for i,wi in enumerate(w):
                c+=float(wi)
                if c>=r:
                    idx=i
                    break
        out.append(pool.pop(idx))
        w=np.delete(w, idx)
    return out


@dataclass
class TacticHit:
    name: str
    score: float
    reason: str


class TacticRegistry:
    """Named heuristic tactics with pluggable scoring callbacks."""

    def __init__(self) -> None:
        self._tactics: list[tuple[str, float, Callable[[dict], float | tuple[float, str]]]]=[]

    def register(
        self,
        name: str,
        fn: Callable[[dict], float | tuple[float, str]],
        weight: float = 1.0,
    ) -> None:
        self._tactics.append((str(name), float(weight), fn))

    def names(self) -> list[str]:
        return [n for n, _, _ in self._tactics]

    def score(self, context: dict) -> tuple[float, list[TacticHit]]:
        total=0.0
        hits: list[TacticHit]=[]
        for name, weight, fn in self._tactics:
            try:
                raw=fn(context)
            except Exception:
                continue
            reason=""
            if isinstance(raw, tuple):
                score=float(raw[0])
                if len(raw)>1:
                    reason=str(raw[1])
            else:
                score=float(raw)
            score*=weight
            if abs(score)<1e-9:
                continue
            total+=score
            hits.append(TacticHit(name=name, score=score, reason=reason))
        hits.sort(key=lambda h: abs(h.score), reverse=True)
        return total, hits

    def update_weight(self, name: str, delta: float, clip_min: float=0.1, clip_max: float=5.0) -> None:
        """Gradient-free weight nudge for a named tactic based on outcome signal."""
        for i,(n,w,fn) in enumerate(self._tactics):
            if n==name:
                self._tactics[i]=(n, float(np.clip(w+float(delta), clip_min, clip_max)), fn)
                break

    def get_weights(self) -> dict:
        """Return current name→weight mapping."""
        return {n: w for n,w,_ in self._tactics}

    def set_weights(self, weights: dict) -> None:
        """Restore weights from a mapping (missing keys keep current value)."""
        self._tactics=[(n, float(weights.get(n, w)), fn) for n,w,fn in self._tactics]


class _TransformerLayer:
    def __init__(self, d_model: int, n_heads: int, ff_mult: int, rng: np.random.Generator) -> None:
        self.d_model=int(d_model)
        self.n_heads=max(1, int(n_heads))
        self.head_dim=max(1, self.d_model//self.n_heads)
        self.ff_dim=max(self.d_model, int(self.d_model*ff_mult))
        scale=np.float32(1.0/math.sqrt(max(1, self.d_model)))
        self.Wq=(rng.standard_normal((self.d_model, self.d_model), dtype=np.float32)*scale).astype(np.float32)
        self.Wk=(rng.standard_normal((self.d_model, self.d_model), dtype=np.float32)*scale).astype(np.float32)
        self.Wv=(rng.standard_normal((self.d_model, self.d_model), dtype=np.float32)*scale).astype(np.float32)
        self.Wo=(rng.standard_normal((self.d_model, self.d_model), dtype=np.float32)*scale).astype(np.float32)
        ff_scale=np.float32(1.0/math.sqrt(max(1, self.d_model)))
        self.W1=(rng.standard_normal((self.d_model, self.ff_dim), dtype=np.float32)*ff_scale).astype(np.float32)
        self.b1=np.zeros(self.ff_dim, dtype=np.float32)
        self.W2=(rng.standard_normal((self.ff_dim, self.d_model), dtype=np.float32)*ff_scale).astype(np.float32)
        self.b2=np.zeros(self.d_model, dtype=np.float32)

    def _attn(self, x: np.ndarray) -> np.ndarray:
                              
        q=x@self.Wq
        k=x@self.Wk
        v=x@self.Wv
        t=x.shape[0]
        h=self.n_heads
        d=self.head_dim
        if h*d!=self.d_model:
                                                 
            use=min(self.d_model, h*d)
            qh=np.zeros((t, h*d), dtype=np.float32); qh[:, :use]=q[:, :use]
            kh=np.zeros((t, h*d), dtype=np.float32); kh[:, :use]=k[:, :use]
            vh=np.zeros((t, h*d), dtype=np.float32); vh[:, :use]=v[:, :use]
            q=qh; k=kh; v=vh
        q=q.reshape(t, h, d).transpose(1, 0, 2)           
        k=k.reshape(t, h, d).transpose(1, 0, 2)
        v=v.reshape(t, h, d).transpose(1, 0, 2)
        scores=np.matmul(q, np.transpose(k, (0, 2, 1))).astype(np.float32) / np.float32(math.sqrt(max(1, d)))
        scores=scores-np.max(scores, axis=-1, keepdims=True)
        probs=np.exp(scores, dtype=np.float32)
        probs=probs/(np.sum(probs, axis=-1, keepdims=True, dtype=np.float32)+1e-9)
        ctx=np.matmul(probs, v)           
        ctx=ctx.transpose(1, 0, 2).reshape(t, h*d)
        if ctx.shape[1]!=self.d_model:
            out=np.zeros((t, self.d_model), dtype=np.float32)
            use=min(self.d_model, ctx.shape[1])
            out[:, :use]=ctx[:, :use]
            ctx=out
        return ctx@self.Wo

    def forward(self, x: np.ndarray) -> np.ndarray:
        a=x+self._attn(_layer_norm(x))
        f=_relu(_layer_norm(a)@self.W1 + self.b1)
        return a + (f@self.W2 + self.b2)

    def save_to(self, out: dict, prefix: str) -> None:
        out[f"{prefix}Wq"]=self.Wq; out[f"{prefix}Wk"]=self.Wk
        out[f"{prefix}Wv"]=self.Wv; out[f"{prefix}Wo"]=self.Wo
        out[f"{prefix}W1"]=self.W1; out[f"{prefix}b1"]=self.b1
        out[f"{prefix}W2"]=self.W2; out[f"{prefix}b2"]=self.b2

    def load_from(self, data: dict, prefix: str) -> bool:
        need=[f"{prefix}Wq", f"{prefix}Wk", f"{prefix}Wv", f"{prefix}Wo", f"{prefix}W1", f"{prefix}b1", f"{prefix}W2", f"{prefix}b2"]
        if not all(k in data for k in need):
            return False
        self.Wq=np.asarray(data[f"{prefix}Wq"], dtype=np.float32)
        self.Wk=np.asarray(data[f"{prefix}Wk"], dtype=np.float32)
        self.Wv=np.asarray(data[f"{prefix}Wv"], dtype=np.float32)
        self.Wo=np.asarray(data[f"{prefix}Wo"], dtype=np.float32)
        self.W1=np.asarray(data[f"{prefix}W1"], dtype=np.float32)
        self.b1=np.asarray(data[f"{prefix}b1"], dtype=np.float32)
        self.W2=np.asarray(data[f"{prefix}W2"], dtype=np.float32)
        self.b2=np.asarray(data[f"{prefix}b2"], dtype=np.float32)
        return True


class _TransformerTower:
    def __init__(
        self,
        input_dim: int,
        d_model: int,
        n_tokens: int,
        n_layers: int,
        n_heads: int,
        ff_mult: int,
        seed: int,
    ) -> None:
        self.input_dim=int(input_dim)
        self.d_model=int(d_model)
        self.n_tokens=max(2, int(n_tokens))
        self.n_layers=max(1, int(n_layers))
        self.n_heads=max(1, int(n_heads))
        self.ff_mult=max(1, int(ff_mult))
        rng=np.random.default_rng(int(seed))
        scale=np.float32(1.0/math.sqrt(max(1, self.input_dim)))
        self.W_in=(rng.standard_normal((self.input_dim, self.n_tokens*self.d_model), dtype=np.float32)*scale).astype(np.float32)
        self.b_in=np.zeros(self.n_tokens*self.d_model, dtype=np.float32)
        self.layers=[_TransformerLayer(self.d_model, self.n_heads, self.ff_mult, rng) for _ in range(self.n_layers)]

    def encode(self, x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        x=np.asarray(x, dtype=np.float32).reshape(-1)
        if x.size!=self.input_dim:
            tmp=np.zeros(self.input_dim, dtype=np.float32)
            use=min(self.input_dim, x.size)
            tmp[:use]=x[:use]
            x=tmp
        tok=(x@self.W_in + self.b_in).reshape(self.n_tokens, self.d_model)
        for lyr in self.layers:
            tok=lyr.forward(tok)
        pooled=np.mean(tok, axis=0, dtype=np.float32)
        return pooled, tok

    def save_to(self, out: dict, prefix: str) -> None:
        out[f"{prefix}input_dim"]=np.array([self.input_dim], dtype=np.int64)
        out[f"{prefix}d_model"]=np.array([self.d_model], dtype=np.int64)
        out[f"{prefix}n_tokens"]=np.array([self.n_tokens], dtype=np.int64)
        out[f"{prefix}n_layers"]=np.array([self.n_layers], dtype=np.int64)
        out[f"{prefix}n_heads"]=np.array([self.n_heads], dtype=np.int64)
        out[f"{prefix}ff_mult"]=np.array([self.ff_mult], dtype=np.int64)
        out[f"{prefix}W_in"]=self.W_in
        out[f"{prefix}b_in"]=self.b_in
        for i,layer in enumerate(self.layers):
            layer.save_to(out, f"{prefix}L{i}_")

    def load_from(self, data: dict, prefix: str) -> bool:
        try:
            if int(data[f"{prefix}input_dim"][0])!=self.input_dim:
                return False
            if int(data[f"{prefix}d_model"][0])!=self.d_model:
                return False
            if int(data[f"{prefix}n_tokens"][0])!=self.n_tokens:
                return False
            if int(data[f"{prefix}n_layers"][0])!=self.n_layers:
                return False
        except Exception:
            return False
        if f"{prefix}W_in" not in data or f"{prefix}b_in" not in data:
            return False
        self.W_in=np.asarray(data[f"{prefix}W_in"], dtype=np.float32)
        self.b_in=np.asarray(data[f"{prefix}b_in"], dtype=np.float32)
        for i,layer in enumerate(self.layers):
            if not layer.load_from(data, f"{prefix}L{i}_"):
                return False
        return True


class BeliefTransformerModel:
    """6-layer transformer estimating opponent hidden-card beliefs."""

    def __init__(
        self,
        input_dim: int,
        d_model: int = 256,
        n_layers: int = 6,
        n_heads: int = 8,
        n_tokens: int = 8,
        ff_mult: int = 2,
        seed: int = 101,
    ) -> None:
        self.input_dim=int(input_dim)
        self.tower=_TransformerTower(
            input_dim=self.input_dim,
            d_model=int(d_model),
            n_tokens=int(n_tokens),
            n_layers=int(n_layers),
            n_heads=int(n_heads),
            ff_mult=int(ff_mult),
            seed=int(seed),
        )
        rng=np.random.default_rng(int(seed)+17)
        scale=np.float32(1.0/math.sqrt(max(1, self.tower.d_model)))
        self.W_card=(rng.standard_normal((self.tower.d_model, 52), dtype=np.float32)*scale).astype(np.float32)
        self.b_card=np.zeros(52, dtype=np.float32)
        self.W_meta=(rng.standard_normal((self.tower.d_model, 8), dtype=np.float32)*scale).astype(np.float32)
        self.b_meta=np.zeros(8, dtype=np.float32)
        self._lr=np.float32(1e-4)

    def infer(self, x: np.ndarray, context: dict | None = None) -> dict:
        pooled,_=self.tower.encode(x)
        logits=(pooled@self.W_card + self.b_card).astype(np.float32)
        context=context or {}
        unknown=set(context.get("unknown_ids", set(range(52))))
        opp_piles_visible=set(context.get("opp_piles_visible", set()))
        opp_void_suits=set(context.get("opp_void_suits", set()))
        suit_of=context.get("suit_of_id")
        if suit_of is None:
            suit_of=lambda cid: cid//13
        for cid in range(52):
            if cid not in unknown:
                logits[cid]=-18.0
                continue
            if cid in opp_piles_visible:
                logits[cid]-=5.0
            if suit_of(cid) in opp_void_suits:
                logits[cid]-=6.0
        probs=_softmax_1d(logits)
        opp_hand_size=max(1, int(context.get("opp_hand_size", 12)))
        hand_prob=np.clip(probs*float(opp_hand_size), 0.0, 1.0)
        suit_prob=np.zeros(4, dtype=np.float32)
        for s in range(4):
            idx0=s*13
            suit_prob[s]=float(np.sum(hand_prob[idx0:idx0+13], dtype=np.float32))/max(1.0, float(opp_hand_size))
        void_prob=np.zeros(4, dtype=np.float32)
        for s in range(4):
            if s in opp_void_suits:
                void_prob[s]=0.98
            else:
                void_prob[s]=float(np.clip(1.0-suit_prob[s], 0.0, 1.0))
        meta=np.tanh(pooled@self.W_meta + self.b_meta).astype(np.float32)
        return {
            "opp_card_prob": hand_prob.astype(np.float32),
            "suit_void_prob": void_prob.astype(np.float32),
            "meta": meta,
            "debug": {
                "unknown_count": len(unknown),
                "opp_void_suits": sorted(list(opp_void_suits)),
                "opp_hand_size": opp_hand_size,
            },
        }

    def train_step(self, x: np.ndarray, opp_card_ids: set, lr: float | None = None) -> float:
        """Supervised belief update: train on actual opponent card set after a match."""
        use_lr=np.float32(float(lr) if lr is not None else float(self._lr))
        pooled,_=self.tower.encode(x)
        logits=(pooled@self.W_card+self.b_card).astype(np.float32)
        target=np.zeros(52, dtype=np.float32)
        for cid in opp_card_ids:
            if 0<=int(cid)<52:
                target[int(cid)]=1.0
        sig=np.float32(1.0)/(np.float32(1.0)+np.exp(-np.clip(logits, np.float32(-15.0), np.float32(15.0))))
        loss=float(-np.mean(target*np.log(sig+np.float32(1e-9))+(np.float32(1.0)-target)*np.log(np.float32(1.0)-sig+np.float32(1e-9))))
        grad=((sig-target)/np.float32(52.0)).astype(np.float32)
        self.W_card-=use_lr*np.outer(pooled, grad).astype(np.float32)
        self.b_card-=use_lr*grad
        return loss

    def save_to(self, out: dict, prefix: str) -> None:
        self.tower.save_to(out, f"{prefix}tower_")
        out[f"{prefix}W_card"]=self.W_card
        out[f"{prefix}b_card"]=self.b_card
        out[f"{prefix}W_meta"]=self.W_meta
        out[f"{prefix}b_meta"]=self.b_meta

    def load_from(self, data: dict, prefix: str) -> bool:
        if not self.tower.load_from(data, f"{prefix}tower_"):
            return False
        need=[f"{prefix}W_card", f"{prefix}b_card", f"{prefix}W_meta", f"{prefix}b_meta"]
        if not all(k in data for k in need):
            return False
        self.W_card=np.asarray(data[f"{prefix}W_card"], dtype=np.float32)
        self.b_card=np.asarray(data[f"{prefix}b_card"], dtype=np.float32)
        self.W_meta=np.asarray(data[f"{prefix}W_meta"], dtype=np.float32)
        self.b_meta=np.asarray(data[f"{prefix}b_meta"], dtype=np.float32)
        return True


class PolicyValueTransformerModel:
    """12-layer transformer producing bid/hand/pile policy logits and value."""

    def __init__(
        self,
        input_dim: int,
        bid_dim: int,
        hand_dim: int = 12,
        pile_dim: int = 4,
        d_model: int = 512,
        n_layers: int = 12,
        n_heads: int = 8,
        n_tokens: int = 10,
        ff_mult: int = 2,
        lr: float = 2.5e-4,
        seed: int = 202,
    ) -> None:
        self.input_dim=int(input_dim)
        self.bid_dim=int(bid_dim)
        self.hand_dim=int(hand_dim)
        self.pile_dim=int(pile_dim)
        self.lr=float(lr)
        self.train_steps=0
        self.tower=_TransformerTower(
            input_dim=self.input_dim,
            d_model=int(d_model),
            n_tokens=int(n_tokens),
            n_layers=int(n_layers),
            n_heads=int(n_heads),
            ff_mult=int(ff_mult),
            seed=int(seed),
        )
        rng=np.random.default_rng(int(seed)+29)
        scale=np.float32(1.0/math.sqrt(max(1, self.tower.d_model)))
        self.W_bid=(rng.standard_normal((self.tower.d_model, self.bid_dim), dtype=np.float32)*scale).astype(np.float32)
        self.b_bid=np.zeros(self.bid_dim, dtype=np.float32)
        self.W_hand=(rng.standard_normal((self.tower.d_model, self.hand_dim), dtype=np.float32)*scale).astype(np.float32)
        self.b_hand=np.zeros(self.hand_dim, dtype=np.float32)
        self.W_pile=(rng.standard_normal((self.tower.d_model, self.pile_dim), dtype=np.float32)*scale).astype(np.float32)
        self.b_pile=np.zeros(self.pile_dim, dtype=np.float32)
        self.W_value=(rng.standard_normal((self.tower.d_model, 1), dtype=np.float32)*scale).astype(np.float32)
        self.b_value=np.zeros(1, dtype=np.float32)

    def _forward(self, x: np.ndarray) -> tuple[dict, np.ndarray]:
        pooled,_=self.tower.encode(x)
        bid_logits=(pooled@self.W_bid + self.b_bid).astype(np.float32)
        hand_logits=(pooled@self.W_hand + self.b_hand).astype(np.float32)
        pile_logits=(pooled@self.W_pile + self.b_pile).astype(np.float32)
        value=float(np.tanh(pooled@self.W_value + self.b_value))
        return {
            "bid_logits": bid_logits,
            "hand_logits": hand_logits,
            "pile_logits": pile_logits,
            "value": value,
        }, pooled

    def infer(self, x: np.ndarray, temperature: float=1.0) -> dict:
        out,_=self._forward(x)
        t=max(0.01, float(temperature))
        return {
            "bid_logits": out["bid_logits"].astype(np.float64),
            "hand_logits": out["hand_logits"].astype(np.float64),
            "pile_logits": out["pile_logits"].astype(np.float64),
            "bid_probs": _softmax_1d(out["bid_logits"]/t).astype(np.float64),
            "hand_probs": _softmax_1d(out["hand_logits"]/t).astype(np.float64),
            "pile_probs": _softmax_1d(out["pile_logits"]/t).astype(np.float64),
            "value": float(out["value"]),
        }

    def train_step(
        self,
        x: np.ndarray,
        policy_head: str | None = None,
        action_idx: int | None = None,
        value_target: float | None = None,
        policy_weight: float = 1.0,
        value_weight: float = 0.65,
        advantage: float | None = None,
    ) -> tuple[float, float]:
        out,pooled=self._forward(x)
        pol_loss=0.0
        val_loss=0.0
        p_w=float(policy_weight)
        v_w=float(value_weight)
        adv_scale=float(np.clip(float(advantage), -3.0, 3.0)) if advantage is not None else 1.0
        if policy_head is not None and action_idx is not None:
            a=int(action_idx)
            if policy_head=="bid" and 0<=a<self.bid_dim:
                p=_softmax_1d(out["bid_logits"])
                pol_loss=float(-math.log(max(1e-9, float(p[a]))))
                grad=(p.copy()).astype(np.float32)
                grad[a]-=1.0
                grad*=p_w*adv_scale
                self.W_bid-=self.lr*np.outer(pooled, grad)
                self.b_bid-=self.lr*grad
            elif policy_head=="hand" and 0<=a<self.hand_dim:
                p=_softmax_1d(out["hand_logits"])
                pol_loss=float(-math.log(max(1e-9, float(p[a]))))
                grad=(p.copy()).astype(np.float32)
                grad[a]-=1.0
                grad*=p_w*adv_scale
                self.W_hand-=self.lr*np.outer(pooled, grad)
                self.b_hand-=self.lr*grad
            elif policy_head=="pile" and 0<=a<self.pile_dim:
                p=_softmax_1d(out["pile_logits"])
                pol_loss=float(-math.log(max(1e-9, float(p[a]))))
                grad=(p.copy()).astype(np.float32)
                grad[a]-=1.0
                grad*=p_w*adv_scale
                self.W_pile-=self.lr*np.outer(pooled, grad)
                self.b_pile-=self.lr*grad
        if value_target is not None:
            target=float(value_target)
            pred=float(out["value"])
            err=np.float32(pred-target)
            val_loss=float(err*err)
            d_raw=np.float32(2.0*err*(1.0-pred*pred)*v_w)
            self.W_value-=self.lr*(pooled.reshape(-1, 1)*d_raw)
            self.b_value-=self.lr*np.array([d_raw], dtype=np.float32)
        self.train_steps+=1
        return pol_loss, val_loss

    def save_to(self, out: dict, prefix: str) -> None:
        out[f"{prefix}train_steps"]=np.array([self.train_steps], dtype=np.int64)
        out[f"{prefix}bid_dim"]=np.array([self.bid_dim], dtype=np.int64)
        out[f"{prefix}hand_dim"]=np.array([self.hand_dim], dtype=np.int64)
        out[f"{prefix}pile_dim"]=np.array([self.pile_dim], dtype=np.int64)
        out[f"{prefix}lr"]=np.array([self.lr], dtype=np.float32)
        self.tower.save_to(out, f"{prefix}tower_")
        out[f"{prefix}W_bid"]=self.W_bid; out[f"{prefix}b_bid"]=self.b_bid
        out[f"{prefix}W_hand"]=self.W_hand; out[f"{prefix}b_hand"]=self.b_hand
        out[f"{prefix}W_pile"]=self.W_pile; out[f"{prefix}b_pile"]=self.b_pile
        out[f"{prefix}W_value"]=self.W_value; out[f"{prefix}b_value"]=self.b_value

    def load_from(self, data: dict, prefix: str) -> bool:
        try:
            if int(data[f"{prefix}bid_dim"][0])!=self.bid_dim:
                return False
            if int(data[f"{prefix}hand_dim"][0])!=self.hand_dim:
                return False
            if int(data[f"{prefix}pile_dim"][0])!=self.pile_dim:
                return False
        except Exception:
            return False
        if not self.tower.load_from(data, f"{prefix}tower_"):
            return False
        need=[f"{prefix}W_bid", f"{prefix}b_bid", f"{prefix}W_hand", f"{prefix}b_hand", f"{prefix}W_pile", f"{prefix}b_pile", f"{prefix}W_value", f"{prefix}b_value"]
        if not all(k in data for k in need):
            return False
        self.W_bid=np.asarray(data[f"{prefix}W_bid"], dtype=np.float32)
        self.b_bid=np.asarray(data[f"{prefix}b_bid"], dtype=np.float32)
        self.W_hand=np.asarray(data[f"{prefix}W_hand"], dtype=np.float32)
        self.b_hand=np.asarray(data[f"{prefix}b_hand"], dtype=np.float32)
        self.W_pile=np.asarray(data[f"{prefix}W_pile"], dtype=np.float32)
        self.b_pile=np.asarray(data[f"{prefix}b_pile"], dtype=np.float32)
        self.W_value=np.asarray(data[f"{prefix}W_value"], dtype=np.float32)
        self.b_value=np.asarray(data[f"{prefix}b_value"], dtype=np.float32)
        self.train_steps=int(data[f"{prefix}train_steps"][0]) if f"{prefix}train_steps" in data else 0
        return True


class HybridJarvisModel:
    """Belief + policy/value hybrid stack with unified infer/train API."""

    def __init__(
        self,
        state_dim: int,
        bid_dim: int,
        hand_dim: int = 12,
        pile_dim: int = 4,
        lr: float = 2.5e-4,
    ) -> None:
        self.state_dim=int(state_dim)
        self.belief_dim=52+4+8
        self.belief=BeliefTransformerModel(
            input_dim=self.state_dim,
            d_model=256,
            n_layers=6,
            n_heads=8,
            n_tokens=8,
            ff_mult=2,
            seed=601,
        )
        self.policy=PolicyValueTransformerModel(
            input_dim=self.state_dim+self.belief_dim,
            bid_dim=int(bid_dim),
            hand_dim=int(hand_dim),
            pile_dim=int(pile_dim),
            d_model=512,
            n_layers=12,
            n_heads=8,
            n_tokens=10,
            ff_mult=2,
            lr=float(lr),
            seed=911,
        )
        self.train_steps=self.policy.train_steps

    def _augment(self, x: np.ndarray, context: dict | None) -> tuple[np.ndarray, dict]:
        base=np.asarray(x, dtype=np.float32).reshape(-1)
        if base.size!=self.state_dim:
            tmp=np.zeros(self.state_dim, dtype=np.float32)
            use=min(self.state_dim, base.size)
            tmp[:use]=base[:use]
            base=tmp
        belief=self.belief.infer(base, context=context or {})
        aug=np.concatenate(
            [base, belief["opp_card_prob"], belief["suit_void_prob"], belief["meta"]],
            axis=0,
            dtype=np.float32,
        )
        return aug, belief

    def infer(self, x: np.ndarray, context: dict | None = None, temperature: float=1.0) -> dict:
        aug,belief=self._augment(x, context)
        out=self.policy.infer(aug, temperature=temperature)
        out["belief"]=belief
        out["architecture"]={
            "belief_transformer_layers": 6,
            "policy_value_transformer_layers": 12,
            "policy_value_d_model": 512,
            "policy_value_heads": 8,
        }
        return out

    def train_step(
        self,
        x: np.ndarray,
        policy_head: str | None = None,
        action_idx: int | None = None,
        value_target: float | None = None,
        policy_weight: float = 1.0,
        value_weight: float = 0.65,
        context: dict | None = None,
        advantage: float | None = None,
    ) -> tuple[float, float]:
        aug,_=self._augment(x, context)
        out=self.policy.train_step(
            aug,
            policy_head=policy_head,
            action_idx=action_idx,
            value_target=value_target,
            policy_weight=policy_weight,
            value_weight=value_weight,
            advantage=advantage,
        )
        self.train_steps=self.policy.train_steps
        return out

    def train_belief_step(self, x: np.ndarray, opp_card_ids: set, context: dict | None = None) -> float:
        """Train the belief tower on the actual opponent card set observed after a match."""
        base=np.asarray(x, dtype=np.float32).reshape(-1)
        if base.size!=self.state_dim:
            tmp=np.zeros(self.state_dim, dtype=np.float32)
            use=min(self.state_dim, base.size)
            tmp[:use]=base[:use]
            base=tmp
        return self.belief.train_step(base, opp_card_ids)

    def save(self, path: str) -> None:
        payload={}
        payload["hybrid_version"]=np.array([1], dtype=np.int64)
        payload["state_dim"]=np.array([self.state_dim], dtype=np.int64)
        payload["belief_dim"]=np.array([self.belief_dim], dtype=np.int64)
        self.belief.save_to(payload, "belief_")
        self.policy.save_to(payload, "policy_")
        np.savez(path, **payload)

    def load(self, path: str) -> bool:
        if not os.path.exists(path):
            return False
        try:
            data=np.load(path)
        except Exception:
            return False
        try:
            if int(data["hybrid_version"][0])!=1:
                return False
            if int(data["state_dim"][0])!=self.state_dim:
                return False
        except Exception:
            return False
        ok_b=self.belief.load_from(data, "belief_")
        ok_p=self.policy.load_from(data, "policy_")
        self.train_steps=self.policy.train_steps
        return bool(ok_b and ok_p)
