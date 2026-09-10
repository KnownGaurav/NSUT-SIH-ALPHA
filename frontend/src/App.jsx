import React, { useState, useEffect } from 'react'
import RailwayMap from './components/RailwayMap'
import StationTimeline from './components/StationTimeline'
import ControlRoomView from './components/ControlRoomView'
import AnalyticsView from './components/AnalyticsView'
import StationOperationsView from './components/StationOperationsView'
import PassengerDisplayView from './components/PassengerDisplayView'

export default function App() {
  const [viewMode, setViewMode] = useState('control_room') // 'control_room' | 'tracking' | 'analytics' | 'station_ops' | 'passenger_led'
  const [trains, setTrains] = useState([])
  const [selectedTrainNumber, setSelectedTrainNumber] = useState('')
  const [trainDetail, setTrainDetail] = useState(null)
  const [routeData, setRouteData] = useState(null)
  const [livePosition, setLivePosition] = useState(null)
  const [baselineData, setBaselineData] = useState(null)
  const [dynamicEtaData, setDynamicEtaData] = useState(null)
  const [healthData, setHealthData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [eventTriggering, setEventTriggering] = useState(false)
  const [lastEventMsg, setLastEventMsg] = useState('')

  // 1. Initial Load: Fetch health and trains list
  useEffect(() => {
    async function init() {
      try {
        setLoading(true)
        const [hRes, tRes] = await Promise.all([
          fetch('/api/health'),
          fetch('/api/trains')
        ])

        if (hRes.ok) setHealthData(await hRes.json())
        if (tRes.ok) {
          const trainsList = await tRes.json()
          setTrains(trainsList)
          if (trainsList.length > 0) {
            setSelectedTrainNumber(trainsList[0].train_number)
          }
        }
      } catch (err) {
        setError(err.message || 'Failed to initialize tracking platform')
      } finally {
        setLoading(false)
      }
    }
    init()
  }, [])

  // 2. Fetch train details and static route when selected train changes
  useEffect(() => {
    if (!selectedTrainNumber) return

    // Immediately clear previous train's stale data to avoid showing old train's delay/speed/positions
    setLivePosition(null)
    setBaselineData(null)
    setDynamicEtaData(null)
    setRouteData(null)

    async function fetchTrainMetadata() {
      try {
        const [dRes, rRes] = await Promise.all([
          fetch(`/api/trains/${selectedTrainNumber}`),
          fetch(`/api/trains/${selectedTrainNumber}/route`)
        ])

        if (dRes.ok) setTrainDetail(await dRes.json())
        if (rRes.ok) setRouteData(await rRes.json())
      } catch (err) {
        console.error('Error loading train metadata:', err)
      }
    }

    fetchTrainMetadata()
  }, [selectedTrainNumber])

  const [wsConnected, setWsConnected] = useState(false)
  const [lastEtaUpdateAlert, setLastEtaUpdateAlert] = useState(null)

  // 3. WebSocket Connection for Instant Real-Time ETA & Telemetry Updates
  useEffect(() => {
    if (!selectedTrainNumber) return

    let ws = null
    let reconnectTimeout = null
    let isCancelled = false

    // Initial REST hydration
    async function initialFetch() {
      try {
        const [pRes, bRes, eRes] = await Promise.all([
          fetch(`/api/trains/${selectedTrainNumber}/position`),
          fetch(`/api/trains/${selectedTrainNumber}/eta/baseline`),
          fetch(`/api/trains/${selectedTrainNumber}/eta`)
        ])
        if (isCancelled) return
        if (pRes.ok) setLivePosition(await pRes.json())
        if (bRes.ok) setBaselineData(await bRes.json())
        if (eRes.ok) setDynamicEtaData(await eRes.json())
      } catch (err) {
        if (!isCancelled) console.error('Initial fetch error:', err)
      }
    }
    initialFetch()

    function connectWebSocket() {
      if (isCancelled) return
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const wsUrl = `${protocol}//${window.location.host}/ws/trains/${selectedTrainNumber}`

      ws = new WebSocket(wsUrl)

      ws.onopen = () => {
        if (!isCancelled) {
          setWsConnected(true)
          console.log(`WebSocket connected for train ${selectedTrainNumber}`)
        }
      }

      ws.onmessage = (event) => {
        if (isCancelled) return
        try {
          const data = JSON.parse(event.data)
          // Guard: ignore messages for a different train
          if (data.train_number && data.train_number !== selectedTrainNumber) {
            return
          }

          if (data.stations) {
            setDynamicEtaData(data)
            // If ETA changes occurred, trigger subtle notice
            if (data.has_eta_update) {
              setLastEtaUpdateAlert(data.update_reason || 'ETA UPDATED')
              setTimeout(() => setLastEtaUpdateAlert(null), 4000)
            }
          }
          if (data.latitude && data.longitude) {
            setLivePosition(prev => ({
              ...prev,
              train_number: data.train_number || selectedTrainNumber,
              timestamp: data.generated_at || new Date().toISOString(),
              latitude: data.latitude,
              longitude: data.longitude,
              speed_kmh: data.speed_kmh ?? prev?.speed_kmh ?? 100.0,
              current_delay_minutes: data.current_delay_minutes ?? prev?.current_delay_minutes ?? 0.0,
              current_station: data.current_station,
              next_station: data.next_station,
              operational_event: data.operational_event || prev?.operational_event || 'NORMAL_OPERATION',
              weather: data.weather || prev?.weather,
              congestion: data.congestion || prev?.congestion
            }))
          }
        } catch (err) {
          console.error('WS message parsing error:', err)
        }
      }

      ws.onclose = () => {
        setWsConnected(false)
        if (!isCancelled) {
          reconnectTimeout = setTimeout(connectWebSocket, 2000)
        }
      }

      ws.onerror = () => {
        ws.close()
      }
    }

    connectWebSocket()

    return () => {
      isCancelled = true
      if (reconnectTimeout) clearTimeout(reconnectTimeout)
      if (ws) ws.close()
    }
  }, [selectedTrainNumber])

  // 4. Trigger Simulation Events Handler
  const handleTriggerEvent = async (eventName) => {
    if (!selectedTrainNumber) return
    setEventTriggering(true)
    try {
      const res = await fetch('/api/simulator/event', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          train_number: selectedTrainNumber,
          event: eventName
        })
      })
      if (res.ok) {
        const data = await res.json()
        setLastEventMsg(`Applied ${eventName} (Speed: ${data.new_speed_kmh} km/h)`)
        // Fast refresh position
        const pRes = await fetch(`/api/trains/${selectedTrainNumber}/position`)
        if (pRes.ok) setLivePosition(await pRes.json())
      }
    } catch (err) {
      console.error('Failed to trigger event:', err)
    } finally {
      setEventTriggering(false)
    }
  }

  // 5. Reset Train Position
  const handleResetTrain = async () => {
    if (!selectedTrainNumber) return
    setEventTriggering(true)
    try {
      await fetch('/api/simulator/reset', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ train_number: selectedTrainNumber })
      })
      setLastEventMsg('Train reset to origin')
      const pRes = await fetch(`/api/trains/${selectedTrainNumber}/position`)
      if (pRes.ok) setLivePosition(await pRes.json())
    } catch (err) {
      console.error('Failed to reset train:', err)
    } finally {
      setEventTriggering(false)
    }
  }

  const [customSearchInput, setCustomSearchInput] = useState('')
  const [searchingLiveTrain, setSearchingLiveTrain] = useState(false)

  // Free-text train search handler
  const handleLiveSearch = async (e) => {
    e.preventDefault()
    const query = customSearchInput.trim()
    if (!query) return

    setSearchingLiveTrain(true)
    try {
      const res = await fetch(`/api/trains/search?q=${encodeURIComponent(query)}`)
      if (res.ok) {
        const found = await res.json()
        if (found && found.length > 0) {
          const matched = found[0]
          // Add to train list if not present
          setTrains(prev => {
            const exists = prev.some(t => t.train_number === matched.train_number)
            return exists ? prev : [matched, ...prev]
          })
          setSelectedTrainNumber(matched.train_number)
          setCustomSearchInput('')
        } else {
          alert(`No train found matching "${query}". Please check the 5-digit train number.`)
        }
      }
    } catch (err) {
      console.error('Search error:', err)
    } finally {
      setSearchingLiveTrain(false)
    }
  }

  const isLiveRailRadar = (livePosition?.data_source === 'RAILRADAR_LIVE') || (healthData?.provider === 'railradar')
  const isSimulation = !isLiveRailRadar && ((livePosition?.data_source === 'SIMULATION') || (healthData?.is_simulation ?? true))
  const delayMinutes = livePosition?.current_delay_minutes ?? 0
  const delayStatus = livePosition?.delay_status || 'on_time'

  // Delay semantic badge styling
  let delayClass = 'delay-on-time'
  let delayLabel = 'ON TIME'
  if (delayStatus === 'moderate') {
    delayClass = 'delay-moderate'
    delayLabel = 'MODERATE DELAY'
  } else if (delayStatus === 'severe') {
    delayClass = 'delay-severe'
    delayLabel = 'CRITICAL DELAY'
  }

  if (viewMode === 'control_room') {
    return (
      <ControlRoomView 
        onSwitchToSingleTrainView={(trainNum) => {
          if (trainNum) setSelectedTrainNumber(trainNum)
          setViewMode('tracking')
        }} 
        onOpenAnalytics={() => setViewMode('analytics')}
        onOpenStationOps={() => setViewMode('station_ops')}
        onOpenPassengerLed={() => setViewMode('passenger_led')}
      />
    )
  }

  if (viewMode === 'analytics') {
    return (
      <AnalyticsView 
        onBackToDashboard={() => setViewMode('control_room')} 
      />
    )
  }

  if (viewMode === 'station_ops') {
    return (
      <StationOperationsView 
        onBackToDashboard={() => setViewMode('control_room')}
        onSwitchToSingleTrainView={(trainNum) => {
          if (trainNum) setSelectedTrainNumber(trainNum)
          setViewMode('tracking')
        }}
        onOpenAnalytics={() => setViewMode('analytics')}
        onOpenPassengerLed={() => setViewMode('passenger_led')}
      />
    )
  }

  if (viewMode === 'passenger_led') {
    return (
      <PassengerDisplayView
        onBackToDashboard={() => setViewMode('control_room')}
        onOpenStationOps={() => setViewMode('station_ops')}
        onOpenAnalytics={() => setViewMode('analytics')}
      />
    )
  }

  return (
    <div className="app-container">
      {/* Top App Header */}
      <header className="ops-header">
        <div className="ops-brand">
          <div className="ops-emblem">IR</div>
          <div className="ops-title-group">
            <h1>Dynamic Railway ETA Prediction Platform</h1>
            <p>Ministry of Railways &bull; SIH 2026 Problem ID: 26028</p>
          </div>
        </div>

        {/* View Switchers */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <button 
            className="btn btn-primary"
            style={{ fontSize: '0.72rem', padding: '0.35rem 0.65rem' }}
            onClick={() => setViewMode('control_room')}
          >
            &#9638; Control Room View
          </button>

          <button 
            className="btn"
            style={{ fontSize: '0.72rem', padding: '0.35rem 0.65rem', borderColor: '#10b981', color: '#34d399' }}
            onClick={() => setViewMode('station_ops')}
          >
            &#128649; Station Operations
          </button>

          <button 
            className="btn"
            style={{ fontSize: '0.72rem', padding: '0.35rem 0.65rem', borderColor: '#0284c7', color: '#38bdf8' }}
            onClick={() => setViewMode('analytics')}
          >
            &#128202; Model Analytics
          </button>

          <button 
            className="btn"
            style={{ fontSize: '0.72rem', padding: '0.35rem 0.65rem', borderColor: '#d97706', color: '#fbbf24' }}
            onClick={() => setViewMode('passenger_led')}
          >
            &#128250; Passenger LED Display
          </button>
        </div>

        {/* Train Search / Live Free-Text Input & Selector */}
        <div className="search-container" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <form onSubmit={handleLiveSearch} style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
            <input 
              type="text"
              placeholder="Search train no (e.g. 12002)..."
              value={customSearchInput}
              onChange={(e) => setCustomSearchInput(e.target.value)}
              className="ops-select"
              style={{ width: '175px', padding: '0.3rem 0.5rem', fontSize: '0.75rem', height: '28px' }}
            />
            <button 
              type="submit" 
              className="btn btn-primary" 
              style={{ padding: '0.25rem 0.5rem', fontSize: '0.7rem', height: '28px' }}
              disabled={searchingLiveTrain}
            >
              {searchingLiveTrain ? '...' : 'Track'}
            </button>
          </form>

          <select 
            id="train-select"
            className="ops-select"
            value={selectedTrainNumber}
            onChange={(e) => setSelectedTrainNumber(e.target.value)}
            style={{ maxWidth: '240px' }}
          >
            {trains.map((t) => (
              <option key={t.train_number} value={t.train_number}>
                {t.train_number} - {t.train_name}
              </option>
            ))}
          </select>
        </div>

        {/* Top Provenance & Health Badges */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
          {/* Explicit Data Source Provenance */}
          <span 
            className={`badge ${isLiveRailRadar ? 'badge-ok' : isSimulation ? 'badge-demo' : 'badge-live'}`}
            style={isLiveRailRadar ? { backgroundColor: '#064e3b', borderColor: '#059669', color: '#34d399' } : {}}
          >
            <span className="dot"></span>
            {isLiveRailRadar ? 'DATA SOURCE: RAIL RADAR LIVE API' : isSimulation ? 'DATA SOURCE: SIMULATION' : 'DATA SOURCE: LIVE IR FEED'}
          </span>

          {/* WebSocket Real-Time Connection Indicator */}
          <span className={`badge ${wsConnected ? 'badge-ok' : 'badge-demo'}`}>
            <span className="dot"></span>
            {wsConnected ? 'WS LIVE FEED' : 'WS RECONNECTING...'}
          </span>

          {/* Service Health */}
          <span className="badge badge-ok">
            <span className="dot"></span>
            API ONLINE
          </span>
        </div>
      </header>

      {/* Subtle Real-Time ETA Update Banner if changes detected */}
      {lastEtaUpdateAlert && (
        <div style={{
          backgroundColor: '#064e3b',
          borderBottom: '1px solid #059669',
          color: '#34d399',
          padding: '0.4rem 1.25rem',
          fontSize: '0.75rem',
          fontFamily: 'var(--font-mono)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          animation: 'eta-subtle-glow 2s ease-in-out'
        }}>
          <span>
            <strong>[REAL-TIME ETA DISPATCH]</strong> {lastEtaUpdateAlert}
          </span>
          <span style={{ fontSize: '0.68rem', color: '#a7f3d0' }}>
            AUTO-UPDATED &bull; NO REFRESH REQUIRED
          </span>
        </div>
      )}

      {/* Main Workspace */}
      <main className="ops-workspace">
        {error && (
          <div style={{ padding: '0.75rem 1rem', background: '#450a0a', border: '1px solid #991b1b', color: '#fca5a5', fontSize: '0.8rem', fontFamily: 'var(--font-mono)' }}>
            [ERROR] {error}
          </div>
        )}

        {/* Main Grid: Left = Railway Map, Right = Telemetry & Disruption Controls */}
        <div className="tracking-grid">
          {/* Primary Visual Element: Railway Map */}
          <section className="panel" style={{ flex: 1, minHeight: '540px' }}>
            <div className="panel-header">
              <h2>
                Railway GIS Route Tracking &bull; {selectedTrainNumber} {trainDetail?.train_name}
              </h2>
              <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                {livePosition?.timestamp ? `UPDATED: ${new Date(livePosition.timestamp).toLocaleTimeString()}` : ''}
              </span>
            </div>

            <div className="map-wrapper">
              <RailwayMap 
                routeData={routeData} 
                livePosition={livePosition} 
                trainInfo={trainDetail} 
              />
            </div>
          </section>

          {/* Side Panel: Train Telemetry & Simulation Controls */}
          <aside className="panel">
            <div className="panel-header">
              <h2>Operational Telemetry</h2>
              <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>STREAMING</span>
            </div>

            <div className="panel-body telemetry-sidebar">
              {/* Train Identity */}
              <div className="metric-card">
                <div className="metric-label">Coaching Train Roster</div>
                <div style={{ fontSize: '1.05rem', fontWeight: 700, color: '#f8fafc', fontFamily: 'var(--font-mono)' }}>
                  {selectedTrainNumber}
                </div>
                <div style={{ fontSize: '0.82rem', color: '#cbd5e1', marginTop: '0.15rem' }}>
                  {trainDetail?.train_name || 'Loading...'}
                </div>
                <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
                  {trainDetail?.train_type} &bull; {trainDetail?.source} &rarr; {trainDetail?.destination}
                </div>
              </div>

              {/* Current Speed */}
              <div className="metric-card">
                <div className="metric-label">Instantaneous Velocity</div>
                <div className="metric-value-large">
                  {livePosition?.speed_kmh !== undefined ? `${livePosition.speed_kmh}` : '--'} <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>KM/H</span>
                </div>
              </div>

              {/* Current Delay with Color Semantics */}
              <div className="metric-card">
                <div className="metric-label">Current Sectional Delay</div>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.5rem' }}>
                  <div className="metric-value-large" style={{ color: delayStatus === 'on_time' ? '#22c55e' : delayStatus === 'moderate' ? '#f59e0b' : '#ef4444' }}>
                    {delayMinutes > 0 ? `+${delayMinutes}` : delayMinutes}
                  </div>
                  <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>MINS</span>
                </div>
                <div className={`delay-badge ${delayClass}`}>
                  <span className="dot"></span>
                  {delayLabel}
                </div>
              </div>

              {/* Section & Stations */}
              <div className="metric-card">
                <div className="metric-label">Current Track Block</div>
                <div style={{ fontSize: '0.85rem', fontWeight: 600, color: '#f8fafc', fontFamily: 'var(--font-mono)' }}>
                  {livePosition?.current_station || '--'} &rarr; {livePosition?.next_station || '--'}
                </div>
                <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', marginTop: '0.2rem' }}>
                  Next Stop: <strong style={{ color: '#38bdf8' }}>{livePosition?.next_station_name || livePosition?.next_station || 'N/A'}</strong>
                </div>
              </div>

              {/* Deterministic Explanation Card: WHY DID ETA CHANGE? */}
              {dynamicEtaData?.explanation && (
                <div className={`explanation-card ${
                  dynamicEtaData.explanation.direction === 'DELAY_INCREASED' ? 'delayed' :
                  dynamicEtaData.explanation.direction === 'DELAY_REDUCED' ? 'recovered' : ''
                }`}>
                  <div className="explanation-header">
                    <span className="explanation-title">
                      <span>WHY DID ETA CHANGE?</span>
                    </span>
                    <span style={{ fontSize: '0.65rem', fontFamily: 'var(--font-mono)', color: '#94a3b8' }}>
                      {dynamicEtaData.explanation.station_code}
                    </span>
                  </div>

                  <div className="explanation-summary">
                    {dynamicEtaData.explanation.summary}
                  </div>

                  {dynamicEtaData.explanation.previous_eta && (
                    <div style={{ fontSize: '0.66rem', fontFamily: 'var(--font-mono)', color: '#facc15', marginBottom: '0.35rem' }}>
                      Shift: {dynamicEtaData.explanation.shift_minutes > 0 ? `+${dynamicEtaData.explanation.shift_minutes}` : dynamicEtaData.explanation.shift_minutes} min
                    </div>
                  )}

                  {dynamicEtaData.explanation.contributing_factors?.length > 0 && (
                    <div className="factor-list">
                      <div style={{ fontSize: '0.64rem', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.4px', fontWeight: 600 }}>
                        Contributing Factors:
                      </div>
                      {dynamicEtaData.explanation.contributing_factors.map((factor, idx) => (
                        <div key={idx} className="factor-item">
                          <div>
                            <span className={`factor-tag ${factor.category}`}>{factor.category}</span>
                            <span style={{ color: '#e2e8f0' }}>{factor.impact_description}</span>
                          </div>
                          <div className="factor-evidence">
                            &bull; {factor.metric_evidence}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Disruption Simulator Controller */}
              <div className="metric-card" style={{ border: '1px solid #334155' }}>
                <div className="metric-label" style={{ color: '#38bdf8' }}>Demo Disruption Events</div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.35rem', marginTop: '0.4rem' }}>
                  <button 
                    className="btn" 
                    style={{ fontSize: '0.7rem', padding: '0.35rem 0.4rem', justifyContent: 'center' }}
                    onClick={() => handleTriggerEvent('NORMAL_OPERATION')}
                    disabled={eventTriggering}
                  >
                    Normal
                  </button>
                  <button 
                    className="btn" 
                    style={{ fontSize: '0.7rem', padding: '0.35rem 0.4rem', justifyContent: 'center', borderColor: '#d97706', color: '#f59e0b' }}
                    onClick={() => handleTriggerEvent('SPEED_RESTRICTION')}
                    disabled={eventTriggering}
                  >
                    Caution
                  </button>
                  <button 
                    className="btn" 
                    style={{ fontSize: '0.7rem', padding: '0.35rem 0.4rem', justifyContent: 'center', borderColor: '#b45309', color: '#fbbf24' }}
                    onClick={() => handleTriggerEvent('CONGESTION')}
                    disabled={eventTriggering}
                  >
                    Congestion
                  </button>
                  <button 
                    className="btn" 
                    style={{ fontSize: '0.7rem', padding: '0.35rem 0.4rem', justifyContent: 'center', borderColor: '#dc2626', color: '#f87171' }}
                    onClick={() => handleTriggerEvent('UNSCHEDULED_HALT')}
                    disabled={eventTriggering}
                  >
                    Halt (0 km/h)
                  </button>
                </div>
                <div style={{ display: 'flex', gap: '0.35rem', marginTop: '0.35rem' }}>
                  <button 
                    className="btn" 
                    style={{ flex: 1, fontSize: '0.7rem', padding: '0.35rem 0.4rem', justifyContent: 'center', borderColor: '#16a34a', color: '#4ade80' }}
                    onClick={() => handleTriggerEvent('RECOVERY')}
                    disabled={eventTriggering}
                  >
                    Recovery
                  </button>
                  <button 
                    className="btn" 
                    style={{ flex: 1, fontSize: '0.7rem', padding: '0.35rem 0.4rem', justifyContent: 'center' }}
                    onClick={handleResetTrain}
                    disabled={eventTriggering}
                  >
                    Reset
                  </button>
                </div>
                {lastEventMsg && (
                  <div style={{ fontSize: '0.68rem', color: '#94a3b8', marginTop: '0.4rem', fontFamily: 'var(--font-mono)' }}>
                    {lastEventMsg}
                  </div>
                )}
              </div>

              {/* Environmental Weather Card (Open-Meteo) */}
              <div className="metric-card">
                <div className="metric-label" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span>Environmental Conditions</span>
                  <span style={{ fontSize: '0.6rem', color: '#60a5fa' }}>OPEN-METEO</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '0.2rem' }}>
                  <div style={{ fontSize: '0.88rem', fontWeight: 700, color: '#f8fafc' }}>
                    {livePosition?.weather?.weather_condition || dynamicEtaData?.weather?.weather_condition || 'Clear sky'}
                  </div>
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.85rem', color: '#38bdf8', fontWeight: 600 }}>
                    {(livePosition?.weather?.temperature_c ?? dynamicEtaData?.weather?.temperature_c ?? 28.0).toFixed(1)}°C
                  </div>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.68rem', color: 'var(--text-secondary)', marginTop: '0.35rem', fontFamily: 'var(--font-mono)' }}>
                  <span>Rain: {(livePosition?.weather?.precipitation_mm ?? dynamicEtaData?.weather?.precipitation_mm ?? 0.0).toFixed(1)} mm</span>
                  <span>Wind: {(livePosition?.weather?.wind_speed_kmh ?? dynamicEtaData?.weather?.wind_speed_kmh ?? 12.0).toFixed(0)} km/h</span>
                  <span>Vis: {(livePosition?.weather?.visibility_km ?? dynamicEtaData?.weather?.visibility_km ?? 10.0).toFixed(1)} km</span>
                </div>
              </div>

              {/* Network Congestion Indicator */}
              <div className="metric-card">
                <div className="metric-label" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span>Simulated Corridor Congestion</span>
                  <span style={{ 
                    fontSize: '0.65rem', 
                    fontWeight: 700,
                    color: (livePosition?.congestion?.level || dynamicEtaData?.congestion?.level || 'LOW') === 'HIGH' ? '#ef4444' : 
                           (livePosition?.congestion?.level || dynamicEtaData?.congestion?.level || 'LOW') === 'MEDIUM' ? '#f59e0b' : '#22c55e'
                  }}>
                    {livePosition?.congestion?.level || dynamicEtaData?.congestion?.level || 'LOW'}
                  </span>
                </div>
                <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', marginTop: '0.25rem', lineHeight: 1.3 }}>
                  {livePosition?.congestion?.factor_description || dynamicEtaData?.congestion?.factor_description || 'Normal line throughput & permissible sectional headway'}
                </div>
              </div>

              {/* Coordinates Readout */}
              <div className="metric-card">
                <div className="metric-label">GPS Coordinate Feed</div>
                <div className="coord-readout">
                  <span>LAT: {livePosition?.latitude?.toFixed(4) || '--.----'}° N</span>
                  <span>LON: {livePosition?.longitude?.toFixed(4) || '--.----'}° E</span>
                  <span style={{ fontSize: '0.68rem', color: isLiveRailRadar ? '#34d399' : '#f59e0b', fontWeight: 600 }}>
                    {isLiveRailRadar ? 'DATA SOURCE: RAIL RADAR LIVE API' : isSimulation ? 'DATA SOURCE: SIMULATION' : 'DATA SOURCE: LIVE IR FEED'}
                  </span>
                </div>
              </div>
            </div>
          </aside>
        </div>

        {/* Bottom Section: Upcoming Stations Timeline */}
        <section className="panel">
          <div className="panel-header">
            <h2>
              Upcoming Stations Journey Timeline &bull; {selectedTrainNumber}
            </h2>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
              {routeData?.stops?.length || 0} SCHEDULED STOPS
            </span>
          </div>

          <div className="panel-body" style={{ padding: '0.5rem 0.75rem' }}>
            <StationTimeline 
              stops={routeData?.stops || []} 
              currentStationCode={livePosition?.current_station}
              nextStationCode={livePosition?.next_station}
              delayStatus={delayStatus}
              baselineData={baselineData}
              dynamicEtaData={dynamicEtaData}
            />
          </div>
        </section>
      </main>

      {/* Operations Footer */}
      <footer className="ops-footer">
        <div>Indian Railways Dynamic ETA Platform &bull; Phase 8 Dynamic XGBoost ETA Engine</div>
        <div style={{ fontFamily: 'var(--font-mono)' }}>
          DATA SOURCE: SIMULATION (AUTHENTIC IR TIMETABLES &bull; NO LIVE CRIS FEED CLAIMED)
        </div>
      </footer>
    </div>
  )
}
