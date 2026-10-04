import { useEffect, useMemo, useRef, useState } from 'react'
import { CandlestickSeries, ColorType, HistogramSeries, createChart, type CandlestickData, type HistogramData, type IChartApi, type ISeriesApi, type UTCTimestamp } from 'lightweight-charts'
import { fmt } from './ui'

export type ChartTrade={timestamp:number;price:number;amount:number}
type Interval='1m'|'5m'|'15m'|'1h'|'4h'|'1d'
const intervals:Record<Interval,number>={'1m':60,'5m':300,'15m':900,'1h':3600,'4h':14400,'1d':86400}

export function MarketChart({pair,trades}:{pair:string;trades:ChartTrade[]}){
  const container=useRef<HTMLDivElement>(null),chart=useRef<IChartApi|null>(null),candles=useRef<ISeriesApi<'Candlestick'>|null>(null),volume=useRef<ISeriesApi<'Histogram'>|null>(null)
  const [interval,setInterval]=useState<Interval>('15m')
  const bars=useMemo(()=>aggregate(trades,intervals[interval]),[trades,interval])
  useEffect(()=>{
    if(!container.current)return
    const instance=createChart(container.current,{autoSize:true,layout:{background:{type:ColorType.Solid,color:'transparent'},textColor:'#789084',fontSize:10},grid:{vertLines:{color:'rgba(86,120,103,.10)'},horzLines:{color:'rgba(86,120,103,.10)'}},timeScale:{timeVisible:true,secondsVisible:false,borderColor:'rgba(86,120,103,.22)'},rightPriceScale:{borderColor:'rgba(86,120,103,.22)'}})
    const candle=instance.addSeries(CandlestickSeries,{upColor:'#27946c',downColor:'#c66f53',borderVisible:false,wickUpColor:'#27946c',wickDownColor:'#c66f53'})
    candle.priceScale().applyOptions({scaleMargins:{top:.08,bottom:.25}})
    const vol=instance.addSeries(HistogramSeries,{priceFormat:{type:'volume'},priceScaleId:''});vol.priceScale().applyOptions({scaleMargins:{top:.8,bottom:0}})
    chart.current=instance;candles.current=candle;volume.current=vol
    return()=>{instance.remove();chart.current=null;candles.current=null;volume.current=null}
  },[])
  useEffect(()=>{
    candles.current?.setData(bars.map(b=>({time:b.time as UTCTimestamp,open:b.open,high:b.high,low:b.low,close:b.close}) satisfies CandlestickData<UTCTimestamp>))
    volume.current?.setData(bars.map(b=>({time:b.time as UTCTimestamp,value:b.volume,color:b.close>=b.open?'rgba(39,148,108,.28)':'rgba(198,111,83,.28)'}) satisfies HistogramData<UTCTimestamp>))
    if(bars.length)chart.current?.timeScale().fitContent()
  },[bars])
  const last=bars.at(-1)
  return <section className="dex-panel dex-chart"><header><div><h3>{pair} 行情</h3>{last&&<small>O {fmt(last.open,4)} · H {fmt(last.high,4)} · L {fmt(last.low,4)} · C {fmt(last.close,4)}</small>}</div><div className="dex-intervals">{(Object.keys(intervals) as Interval[]).map(i=><button className={i===interval?'active':''} onClick={()=>setInterval(i)} key={i}>{i}</button>)}</div></header><div className="dex-chart-canvas" ref={container}/>{!bars.length&&<div className="dex-chart-empty">等待该交易对的首笔链上成交</div>}</section>
}

function aggregate(trades:ChartTrade[],seconds:number){
  const buckets=new Map<number,{time:number;open:number;high:number;low:number;close:number;volume:number}>()
  for(const trade of [...trades].sort((a,b)=>a.timestamp-b.timestamp)){
    const time=Math.floor(trade.timestamp/seconds)*seconds,current=buckets.get(time)
    if(current){current.high=Math.max(current.high,trade.price);current.low=Math.min(current.low,trade.price);current.close=trade.price;current.volume+=trade.amount}
    else buckets.set(time,{time,open:trade.price,high:trade.price,low:trade.price,close:trade.price,volume:trade.amount})
  }
  return [...buckets.values()]
}
