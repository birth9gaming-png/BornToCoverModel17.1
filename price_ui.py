"""Visible price recovery on the board; no historical reload is required."""
from datetime import datetime,timezone
import streamlit as st
from price_refresh import coverage
from workspace_runtime import start_price_refresh,rerun


def panel(data,secret):
    if data.get('mode')!='connected':return
    now=datetime.now(timezone.utc);counts=coverage(data,now)
    if not counts['games']:return
    key=secret('ODDS_API_KEY');job=st.session_state.get('_price_job')
    st.caption(f"Sportsbook prices: {counts['spread']}/{counts['games']} spreads · {counts['total']}/{counts['games']} totals current")
    if not key:
        st.warning('Live picks need ODDS_API_KEY in Streamlit Secrets. Your saved models and projections are loaded.')
    elif counts['both']<counts['games']:
        messages=list(dict.fromkeys(c['message'] for c in data.get('market_price_checks',{}).values() if c.get('state')!='ok' and c.get('message')))
        st.warning('Some picks are waiting for current sportsbook prices. '+(' '.join(messages) if messages else 'Price recovery runs separately from statistics and learning updates.'))
    if st.session_state.get('_price_error'):st.warning(st.session_state['_price_error'])
    if st.button('Refresh sportsbook prices now',key='refresh_prices_now',disabled=not key or bool(job)):
        start_price_refresh(data,key,now,force=True);rerun()
    with st.expander('Price connection and matching details'):
        st.caption('Refreshes cover every upcoming loaded game. Quotes keep their original bookmaker timestamps; old, future-dated and post-kickoff prices cannot become current picks.')
        for lg in ('CFB','NFL'):
            c=coverage(data,now,lg)
            if not c['games']:continue
            check=data.get('market_price_checks',{}).get(lg,{})
            st.write(lg+f": {c['spread']}/{c['games']} spreads, {c['total']}/{c['games']} totals current")
            st.caption('Last price check: '+str(check.get('checked_at','Not checked yet'))+' · '+check.get('message','Waiting for a price check'))
            diagnostic=data.get('odds_join_diagnostics',{}).get(lg)
            if diagnostic:st.json(diagnostic)
