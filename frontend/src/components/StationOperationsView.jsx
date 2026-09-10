import React, { useState, useEffect } from 'react'

const POPULAR_STATIONS = [
  { code: 'NDLS', name: 'New Delhi', zone: 'NR', platforms: 16 },
  { code: 'CNB', name: 'Kanpur Central', zone: 'NCR', platforms: 10 },
  { code: 'PRYJ', name: 'Prayagraj Junction', zone: 'NCR', platforms: 10 },
  { code: 'BSB', name: 'Varanasi Junction', zone: 'NR', platforms: 9 },
  { code: 'HWH', name: 'Howrah Junction', zone: 'ER', platforms: 23 },
  { code: 'DBG', name: 'Darbhanga Junction', zone: 'ECR', platforms: 5 },
  { code: 'TPTY', name: 'Tirupati', zone: 'SCR', platforms: 6 },
]

export default function StationOperationsView({ 
  onBackToDashboard, 
  onSwitchToSingleTrainView,
  onOpenAnalytics,
  onOpenPassengerLed
}) {
  const [selectedStation, setSelectedStation] = useState('NDLS')
  const [customStationInput, setCustomStationInput] = useState('')
  const [windowHours, setWindowHours] = useState(4)
  const [activeTab, setActiveTab] = useState('grid') // 'grid' | 'table' | 'turnaround'
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [lastUpdated, setLastUpdated] = useState(null)

  const fetchArrivals = async (stationCode, hours) => {
    try {
      setLoading(true)
      setError(null)
      const res = await fetch(`/api/stations/${stationCode}/arrivals?window_hours=${hours}`)
      if (res.ok) {
        const json = await res.json()
        setData(json)
        setLastUpdated(new Date())
      } else {
        const errJson = await res.json().catch(() => ({}))
        setError(errJson.detail || `Failed to fetch arrivals for station ${stationCode}`)
      }
    } catch (err) {
      setError(err.message || 'Network error fetching station operations data')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchArrivals(selectedStation, windowHours)
    const interval = setInterval(() => {
      fetchArrivals(selectedStation, windowHours)
    }, 10000)
    return () => clearInterval(interval)
  }, [selectedStation, windowHours])

  const handleCustomStationSubmit = (e) => {
    e.preventDefault()
    const code = customStationInput.trim().toUpperCase()
    if (code) {
      setSelectedStation(code)
      setCustomStationInput('')
    }
  }

  // Group arrivals by platform for the Grid view
  const arrivalsByPlatform = {}
  const totalPfs = data?.total_platforms || 16
  for (let pf = 1; pf <= totalPfs; pf++) {
    arrivalsByPlatform[`PF-${pf}`] = []
  }

  if (data?.arrivals) {
    data.arrivals.forEach((arr) => {
      const pfKey = arr.assigned_platform || 'PF-1'
      if (!arrivalsByPlatform[pfKey]) {
        arrivalsByPlatform[pfKey] = []
      }
      arrivalsByPlatform[pfKey].push(arr)
    })
  }

  // Count summaries
  const totalMovements = data?.arrivals?.length || 0
  const conflictsCount = data?.active_conflicts_count || 0
  const onTimeCount = data?.arrivals?.filter(a => a.delay_minutes <= 5).length || 0
  const delayedCount = totalMovements - onTimeCount
  const tightTurnarounds = data?.arrivals?.filter(a => 
    a.turnaround_impact?.cleaning_depot_status === 'TIGHT_WINDOW' || 
    a.turnaround_impact?.cleaning_depot_status === 'DELAYED_HANDOVER'
  ).length || 0

  return (
    <div className="station-ops-layout">
      {/* Top Header */}
      <header className="station-ops-header">
        <div className="cr-brand-group">
          <div className="cr-badge" style={{ backgroundColor: '#0284c7' }}>IR-STN-OPS</div>
          <div>
            <div className="cr-title">STATION OPERATIONS &amp; PLATFORM OCCUPANCY SUPERVISION</div>
            <div className="cr-subtitle">
              Dynamic Platform Allocation &bull; Clearance Conflict Detection &bull; Turnaround Depot Scheduling
            </div>
          </div>
        </div>

        {/* Global Nav Buttons */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span 
            className="badge badge-ok"
            style={{ backgroundColor: '#064e3b', borderColor: '#059669', color: '#34d399' }}
          >
            <span className="dot"></span>
            LIVE RADAR &bull; ACTIVE
          </span>

          <button 
            className="btn" 
            style={{ fontSize: '0.72rem', padding: '0.35rem 0.6rem', borderColor: '#0284c7', color: '#38bdf8' }}
            onClick={onOpenAnalytics}
          >
            &#128202; Model Analytics
          </button>

          <button 
            className="btn" 
            style={{ fontSize: '0.72rem', padding: '0.35rem 0.6rem', borderColor: '#d97706', color: '#fbbf24' }}
            onClick={onOpenPassengerLed}
          >
            &#128250; Passenger LED Display
          </button>

          <button 
            className="btn btn-primary" 
            style={{ fontSize: '0.72rem', padding: '0.35rem 0.65rem' }}
            onClick={onBackToDashboard}
          >
            &#9638; Control Room View
          </button>
        </div>
      </header>

      {/* Station Selector Bar & Filters */}
      <div className="station-selector-bar">
        <div className="station-chips-group">
          <span className="station-label">SELECT TERMINAL:</span>
          {POPULAR_STATIONS.map((stn) => (
            <button
              key={stn.code}
              className={`station-chip ${selectedStation === stn.code ? 'active' : ''}`}
              onClick={() => setSelectedStation(stn.code)}
            >
              <strong>{stn.code}</strong>
              <span className="station-chip-sub">({stn.name})</span>
            </button>
          ))}
        </div>

        {/* Custom Station Search */}
        <form onSubmit={handleCustomStationSubmit} style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
          <input
            type="text"
            placeholder="Station code..."
            value={customStationInput}
            onChange={(e) => setCustomStationInput(e.target.value)}
            className="cr-search-input"
            style={{ width: '110px', height: '28px', textTransform: 'uppercase' }}
          />
          <button type="submit" className="btn btn-primary" style={{ padding: '0.2rem 0.5rem', fontSize: '0.7rem', height: '28px' }}>
            Go
          </button>
        </form>

        {/* Window Selector */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginLeft: 'auto' }}>
          <span style={{ fontSize: '0.68rem', color: '#94a3b8' }}>WINDOW:</span>
          {[2, 4, 8, 12].map((hrs) => (
            <button
              key={hrs}
              className={`window-pill ${windowHours === hrs ? 'active' : ''}`}
              onClick={() => setWindowHours(hrs)}
            >
              {hrs}h
            </button>
          ))}
          <button 
            className="btn" 
            style={{ fontSize: '0.68rem', padding: '0.25rem 0.5rem', marginLeft: '0.5rem' }}
            onClick={() => fetchArrivals(selectedStation, windowHours)}
            disabled={loading}
          >
            &#x21bb; Refresh
          </button>
        </div>
      </div>

      {/* Summary KPI Strip */}
      <div className="station-kpi-strip">
        <div className="kpi-box">
          <span className="kpi-label">STATION TERMINAL</span>
          <span className="kpi-value text-sky">
            {data ? `${data.station_name} (${data.station_code})` : selectedStation}
          </span>
          <span className="kpi-sub">{data ? `Zone: ${data.zone} | Total Platforms: ${data.total_platforms}` : '--'}</span>
        </div>

        <div className="kpi-box">
          <span className="kpi-label">UPCOMING MOVEMENTS</span>
          <span className="kpi-value">{totalMovements}</span>
          <span className="kpi-sub">Next {windowHours} Hours Horizon</span>
        </div>

        <div className={`kpi-box ${conflictsCount > 0 ? 'kpi-danger-pulse' : ''}`}>
          <span className="kpi-label">PLATFORM CONFLICTS</span>
          <span className={`kpi-value ${conflictsCount > 0 ? 'text-red' : 'text-green'}`}>
            {conflictsCount}
          </span>
          <span className="kpi-sub">
            {conflictsCount > 0 ? 'Clearance < 25m detected!' : 'All Clear / No Overlaps'}
          </span>
        </div>

        <div className="kpi-box">
          <span className="kpi-label">ON-TIME VS DELAYED</span>
          <div style={{ display: 'flex', gap: '0.6rem', alignItems: 'baseline' }}>
            <span className="kpi-value text-green">{onTimeCount}</span>
            <span style={{ fontSize: '0.8rem', color: '#64748b' }}>/</span>
            <span className="kpi-value text-amber">{delayedCount}</span>
          </div>
          <span className="kpi-sub">{totalMovements > 0 ? Math.round((onTimeCount / totalMovements) * 100) : 100}% Punctuality Rate</span>
        </div>

        <div className="kpi-box">
          <span className="kpi-label">DEPOT TURNAROUND PRESSURE</span>
          <span className={`kpi-value ${tightTurnarounds > 0 ? 'text-amber' : 'text-slate'}`}>
            {tightTurnarounds}
          </span>
          <span className="kpi-sub">Tight / Delayed Cleaning Windows</span>
        </div>
      </div>

      {/* Active Conflict Alert Banner if any conflicts exist */}
      {conflictsCount > 0 && (
        <div className="station-conflict-alert">
          <div className="conflict-icon">&#9888;</div>
          <div style={{ flex: 1 }}>
            <div className="conflict-title">
              CRITICAL OPERATIONAL ALERT: {conflictsCount} PLATFORM CLEARANCE CONFLICT(S) DETECTED
            </div>
            <div className="conflict-desc">
              Dynamic ETA prediction indicates arriving trains will overlap on the same platform within the 25-minute minimum clearance buffer.
              Inspect flagged platforms below to execute dynamic track/platform reassignments.
            </div>
          </div>
        </div>
      )}

      {/* View Mode Tabs */}
      <div className="station-view-tabs">
        <button 
          className={`station-tab-btn ${activeTab === 'grid' ? 'active' : ''}`}
          onClick={() => setActiveTab('grid')}
        >
          &#9638; Platform Occupancy Grid ({totalPfs} PFs)
        </button>
        <button 
          className={`station-tab-btn ${activeTab === 'table' ? 'active' : ''}`}
          onClick={() => setActiveTab('table')}
        >
          &#9776; Arrival &amp; Departure Roster ({totalMovements})
        </button>
        <button 
          className={`station-tab-btn ${activeTab === 'turnaround' ? 'active' : ''}`}
          onClick={() => setActiveTab('turnaround')}
        >
          &#9874; Cleaning Depot &amp; Crew Turnaround ({totalMovements})
        </button>

        {lastUpdated && (
          <span style={{ marginLeft: 'auto', fontSize: '0.65rem', color: '#64748b', fontFamily: 'var(--font-mono)' }}>
            LAST TELEMETRY REFRESH: {lastUpdated.toLocaleTimeString()}
          </span>
        )}
      </div>

      {/* Main Workspace Body */}
      <div className="station-main-body">
        {loading && !data && (
          <div className="analytics-loading" style={{ height: '300px' }}>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.85rem', color: '#38bdf8' }}>
              FETCHING STATION OCCUPANCY TELEMETRY FOR {selectedStation}...
            </div>
          </div>
        )}

        {error && (
          <div style={{ padding: '2rem', textAlign: 'center', color: '#f87171', fontFamily: 'var(--font-mono)' }}>
            [STATION OPS ERROR] {error}
          </div>
        )}

        {/* TAB 1: Platform Occupancy Grid */}
        {activeTab === 'grid' && data && (
          <div className="platform-grid-container">
            {Object.keys(arrivalsByPlatform).map((pfKey) => {
              const trainsOnPf = arrivalsByPlatform[pfKey]
              const hasConflict = trainsOnPf.some(t => t.platform_conflict_flag)
              const isOccupied = trainsOnPf.length > 0

              return (
                <div 
                  key={pfKey} 
                  className={`platform-card ${hasConflict ? 'has-conflict' : isOccupied ? 'is-occupied' : 'is-empty'}`}
                >
                  <div className="platform-header">
                    <span className="platform-tag">{pfKey}</span>
                    <span className="platform-status-label">
                      {hasConflict ? (
                        <span className="status-badge-conflict">&#9888; CONFLICT</span>
                      ) : isOccupied ? (
                        <span className="status-badge-occupied">{trainsOnPf.length} TRAIN(S)</span>
                      ) : (
                        <span className="status-badge-clear">CLEAR</span>
                      )}
                    </span>
                  </div>

                  <div className="platform-trains-list">
                    {trainsOnPf.length === 0 ? (
                      <div className="platform-empty-slot">
                        Platform clear for dynamic reassignment
                      </div>
                    ) : (
                      trainsOnPf.map((train) => (
                        <div 
                          key={train.train_number}
                          className={`platform-train-item ${train.platform_conflict_flag ? 'conflict-pulse' : ''}`}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <span className="stn-train-num">{train.train_number}</span>
                            <span className={`cr-delay-pill status-${train.delay_status === 'on_time' ? 'green' : train.delay_status === 'moderate' ? 'amber' : 'red'}`}>
                              {train.delay_minutes <= 0 ? 'RT 0m' : `+${Math.round(train.delay_minutes)}m`}
                            </span>
                          </div>

                          <div className="stn-train-name">{train.train_name}</div>
                          <div className="stn-train-route">
                            {train.source} &rarr; {train.destination}
                          </div>

                          <div className="stn-time-grid">
                            <div>
                              <div className="stn-time-lbl">SCHED ARR</div>
                              <div className="stn-time-val">{train.scheduled_arrival || train.scheduled_departure || '--:--'}</div>
                            </div>
                            <div>
                              <div className="stn-time-lbl">DYNAMIC ETA</div>
                              <div className="stn-time-val dynamic">{train.dynamic_predicted_eta || '--:--'}</div>
                            </div>
                          </div>

                          {train.platform_conflict_flag && (
                            <div className="platform-conflict-box">
                              <div className="conflict-tag-text">&#9888; OVERLAP HAZARD</div>
                              <div>{train.conflict_reason}</div>
                            </div>
                          )}

                          <div className="stn-action-row">
                            <span className="stn-status-pill">{train.current_status}</span>
                            <button 
                              className="stn-track-btn"
                              onClick={() => onSwitchToSingleTrainView(train.train_number)}
                            >
                              Track &rarr;
                            </button>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        )}

        {/* TAB 2: Arrival & Departure Schedule Table */}
        {activeTab === 'table' && data && (
          <div className="stn-table-wrapper">
            <table className="stn-data-table">
              <thead>
                <tr>
                  <th>PLATFORM</th>
                  <th>TRAIN</th>
                  <th>ROUTE</th>
                  <th>SCHED ARRIVAL</th>
                  <th>DYNAMIC PREDICTED ETA</th>
                  <th>DELAY DELTA</th>
                  <th>STATUS</th>
                  <th>CONFLICT MONITOR</th>
                  <th>ACTION</th>
                </tr>
              </thead>
              <tbody>
                {data.arrivals.length === 0 ? (
                  <tr>
                    <td colSpan="9" style={{ textAlign: 'center', padding: '2rem', color: '#64748b' }}>
                      No scheduled or dynamic arrivals found for {selectedStation} in the {windowHours}h window.
                    </td>
                  </tr>
                ) : (
                  data.arrivals.map((arr) => (
                    <tr key={arr.train_number} className={arr.platform_conflict_flag ? 'table-row-conflict' : ''}>
                      <td>
                        <span className={`pf-badge ${arr.platform_conflict_flag ? 'pf-conflict' : ''}`}>
                          {arr.assigned_platform}
                        </span>
                      </td>
                      <td>
                        <div style={{ fontFamily: 'var(--font-mono)', fontWeight: '700', color: '#f8fafc' }}>
                          {arr.train_number}
                        </div>
                        <div style={{ fontSize: '0.68rem', color: '#94a3b8' }}>{arr.train_name}</div>
                      </td>
                      <td>
                        <span style={{ fontSize: '0.72rem', color: '#cbd5e1' }}>
                          {arr.source} &rarr; {arr.destination}
                        </span>
                        <div style={{ fontSize: '0.65rem', color: '#64748b' }}>
                          {arr.is_destination ? 'Terminating Service' : arr.is_origin ? 'Originating Service' : 'Through Halt'}
                        </div>
                      </td>
                      <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem' }}>
                        {arr.scheduled_arrival || arr.scheduled_departure || '--:--'}
                      </td>
                      <td>
                        <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: '#38bdf8', fontWeight: '700' }}>
                          {arr.dynamic_predicted_eta || '--:--'}
                        </div>
                        <div style={{ fontSize: '0.62rem', color: '#64748b' }}>Continuous ML Forecast</div>
                      </td>
                      <td>
                        <span className={`cr-delay-pill status-${arr.delay_status === 'on_time' ? 'green' : arr.delay_status === 'moderate' ? 'amber' : 'red'}`}>
                          {arr.delay_minutes <= 0 ? 'ON TIME' : `+${Math.round(arr.delay_minutes)} min`}
                        </span>
                      </td>
                      <td>
                        <span className="stn-status-pill">{arr.current_status}</span>
                      </td>
                      <td>
                        {arr.platform_conflict_flag ? (
                          <div style={{ color: '#f87171', fontSize: '0.68rem', fontWeight: '700' }}>
                            &#9888; CONFLICT: {arr.conflict_with_train}
                            <div style={{ fontSize: '0.62rem', color: '#fca5a5', fontWeight: 'normal' }}>
                              {arr.conflict_reason}
                            </div>
                          </div>
                        ) : (
                          <span style={{ color: '#34d399', fontSize: '0.68rem', fontWeight: '600' }}>
                            &check; Clear Buffer
                          </span>
                        )}
                      </td>
                      <td>
                        <button 
                          className="stn-track-btn"
                          onClick={() => onSwitchToSingleTrainView(arr.train_number)}
                        >
                          Supervise
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* TAB 3: Cleaning Depot & Crew Turnaround Readiness */}
        {activeTab === 'turnaround' && data && (
          <div className="turnaround-view-container">
            <div className="turnaround-intro-card">
              <div style={{ fontWeight: '700', fontSize: '0.78rem', color: '#f8fafc', marginBottom: '0.3rem' }}>
                DOWNSTREAM IMPACT: RAKE MAINTENANCE, CREW SCHEDULING &amp; FEEDER LOGISTICS
              </div>
              <p style={{ fontSize: '0.7rem', color: '#94a3b8', lineHeight: 1.4, margin: 0 }}>
                Delays directly compress turn-around windows at terminal yards, jeopardizing scheduled pit-line cleaning,
                catering replenishment, safety checks, and crew duty rosters. The Dynamic ETA model predicts yard handovers
                so station masters and depot supervisors can trigger fast-track maintenance protocols.
              </p>
            </div>

            <div className="turnaround-cards-grid">
              {data.arrivals.map((arr) => {
                const turn = arr.turnaround_impact
                if (!turn) return null

                const isTight = turn.cleaning_depot_status === 'TIGHT_WINDOW'
                const isDelayed = turn.cleaning_depot_status === 'DELAYED_HANDOVER'
                const isOnSchedule = turn.cleaning_depot_status === 'ON_SCHEDULE'

                return (
                  <div 
                    key={arr.train_number}
                    className={`turnaround-card ${isDelayed ? 'border-red' : isTight ? 'border-amber' : 'border-green'}`}
                  >
                    <div className="turnaround-header">
                      <div>
                        <span className="turnaround-train-num">{arr.train_number}</span>
                        <span className="turnaround-train-name">{arr.train_name}</span>
                      </div>
                      <span className={`depot-status-badge ${isOnSchedule ? 'bg-green' : isTight ? 'bg-amber' : 'bg-red'}`}>
                        {turn.cleaning_depot_status.replace('_', ' ')}
                      </span>
                    </div>

                    <div className="turnaround-meta">
                      <div>
                        <span className="meta-lbl">TERMINAL ROLE:</span>
                        <span className="meta-val">{arr.is_destination ? 'Destination Terminal' : arr.is_origin ? 'Originating Train' : 'Through Halt'}</span>
                      </div>
                      <div>
                        <span className="meta-lbl">ASSIGNED PF:</span>
                        <span className="meta-val">{arr.assigned_platform}</span>
                      </div>
                      <div>
                        <span className="meta-lbl">PREDICTED ARRIVAL:</span>
                        <span className="meta-val" style={{ color: '#38bdf8' }}>{arr.dynamic_predicted_eta}</span>
                      </div>
                    </div>

                    <div className="turnaround-progress-section">
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.68rem', marginBottom: '4px' }}>
                        <span style={{ color: '#94a3b8' }}>Available Turnaround Buffer:</span>
                        <strong style={{ fontFamily: 'var(--font-mono)', color: isDelayed ? '#f87171' : isTight ? '#fbbf24' : '#34d399' }}>
                          {turn.available_turnaround_minutes}m / {turn.scheduled_turnaround_minutes}m sched
                        </strong>
                      </div>
                      <div className="turnaround-bar-bg">
                        <div 
                          className={`turnaround-bar-fill ${isDelayed ? 'fill-red' : isTight ? 'fill-amber' : 'fill-green'}`}
                          style={{ width: `${Math.min(100, Math.max(10, (turn.available_turnaround_minutes / turn.scheduled_turnaround_minutes) * 100))}%` }}
                        />
                      </div>
                    </div>

                    <div className="turnaround-footer">
                      <div className="crew-readiness">
                        <span>CREW HANDOVER:</span>
                        <strong className={turn.crew_handover_ready ? 'text-green' : 'text-amber'}>
                          {turn.crew_handover_ready ? ' READY' : ' CRITICAL TIMELINE'}
                        </strong>
                      </div>
                      <div className="depot-release">
                        <span>EST. DEPOT DEPARTURE:</span>
                        <strong style={{ color: '#cbd5e1' }}>{turn.estimated_depot_departure}</strong>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
