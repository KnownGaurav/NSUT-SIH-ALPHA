import React from 'react'

export default function StationTimeline({ stops, currentStationCode, nextStationCode, delayStatus, baselineData, dynamicEtaData }) {
  if (!stops || stops.length === 0) {
    return (
      <div style={{ padding: '1rem', color: 'var(--text-muted)', fontSize: '0.8rem' }}>
        No station timeline available.
      </div>
    )
  }

  // Create lookup maps by station code
  const baselineMap = {}
  if (baselineData?.stations) {
    baselineData.stations.forEach(s => {
      baselineMap[s.station_code] = s
    })
  }

  const dynamicMap = {}
  if (dynamicEtaData?.stations) {
    dynamicEtaData.stations.forEach(s => {
      dynamicMap[s.station_code] = s
    })
  }

  let currentIndex = -1
  if (currentStationCode) {
    currentIndex = stops.findIndex(s => s.station_code === currentStationCode)
  }

  const formatTime = (isoString) => {
    if (!isoString) return '--:--'
    try {
      return new Date(isoString).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    } catch {
      return '--:--'
    }
  }

  return (
    <div className="timeline-container">

      {/* Phase 21: Downstream Corridor Slack Card */}
      {dynamicEtaData && (dynamicEtaData.total_slack_minutes_remaining > 0 || dynamicEtaData.projected_recovery_minutes >= 0) && (
        <div className="corridor-slack-card">
          <div className="corridor-slack-header">
            <span className="corridor-slack-icon">⏱</span>
            <span className="corridor-slack-title">Downstream Corridor Slack Analysis</span>
            <span className="corridor-slack-badge">PHASE 21</span>
          </div>
          <div className="corridor-slack-body">
            <div className="corridor-slack-stat">
              <div className="cslack-val" style={{
                color: dynamicEtaData.total_slack_minutes_remaining >= dynamicEtaData.current_delay_minutes
                  ? '#34d399' : '#f59e0b'
              }}>
                {dynamicEtaData.total_slack_minutes_remaining.toFixed(1)} min
              </div>
              <div className="cslack-lbl">Total Buffer Available</div>
              <div className="cslack-sub">Dwell + sectional timetable slack</div>
            </div>
            <div className="corridor-slack-divider" />
            <div className="corridor-slack-stat">
              <div className="cslack-val" style={{
                color: dynamicEtaData.projected_recovery_minutes > 0 ? '#22c55e' : '#94a3b8'
              }}>
                ~{dynamicEtaData.projected_recovery_minutes.toFixed(1)} min
              </div>
              <div className="cslack-lbl">Expected Recovery</div>
              <div className="cslack-sub">Before terminal destination</div>
            </div>
            <div className="corridor-slack-divider" />
            <div className="corridor-slack-stat">
              <div className="cslack-val" style={{ color: '#38bdf8' }}>
                {dynamicEtaData.current_delay_minutes > 0
                  ? `+${dynamicEtaData.current_delay_minutes.toFixed(1)} min`
                  : 'On Time'}
              </div>
              <div className="cslack-lbl">Current Delay</div>
              <div className="cslack-sub">
                {dynamicEtaData.total_slack_minutes_remaining >= dynamicEtaData.current_delay_minutes
                  ? '✓ Full recovery possible'
                  : '⚠ Partial recovery expected'}
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="timeline-track">
        {stops.map((stop, idx) => {
          const isPassed = currentIndex >= 0 && idx <= currentIndex
          const isCurrent = stop.station_code === currentStationCode
          const isNext = stop.station_code === nextStationCode
          const isOrigin = idx === 0
          const isDestination = idx === stops.length - 1

          const bInfo = baselineMap[stop.station_code]
          const dInfo = dynamicMap[stop.station_code]

          const mlEtaTimeStr = dInfo?.predicted_eta || dInfo?.dynamic_eta ? formatTime(dInfo.predicted_eta || dInfo.dynamic_eta) : null
          const baseEtaTimeStr = bInfo?.baseline_eta ? formatTime(bInfo.baseline_eta) : null
          const lowerTimeStr = dInfo?.lower_bound ? formatTime(dInfo.lower_bound) : null
          const upperTimeStr = dInfo?.upper_bound ? formatTime(dInfo.upper_bound) : null

          const diffMins = dInfo?.delta_vs_baseline_minutes

          let nodeClass = 'timeline-node-upcoming'
          if (isPassed) nodeClass = 'timeline-node-passed'
          if (isCurrent) nodeClass = 'timeline-node-current'
          if (isNext) nodeClass = 'timeline-node-next'

          return (
            <div key={stop.station_code} className={`timeline-step ${nodeClass}`}>
              {/* Step indicator circle and line */}
              <div className="step-header">
                <div className="step-marker">
                  {isCurrent ? '●' : stop.sequence}
                </div>
                {idx < stops.length - 1 && (
                  <div className={`step-connector ${isPassed && idx < currentIndex ? 'connector-passed' : ''}`} />
                )}
              </div>

              {/* Station Details */}
              <div className="step-content">
                <div className="step-code">
                  {stop.station_code}
                  {isOrigin && <span className="step-tag">ORIGIN</span>}
                  {isDestination && <span className="step-tag">TERM</span>}
                  {isNext && <span className="step-tag-next">NEXT</span>}
                </div>
                <div className="step-name" title={stop.station_name}>{stop.station_name}</div>
                
                <div className="step-times">
                  <span>Sched: {stop.scheduled_arrival || stop.scheduled_departure || '--:--'}</span>

                  {!isPassed && mlEtaTimeStr && (
                    <div style={{ marginTop: '0.2rem' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', flexWrap: 'wrap' }}>
                        <span style={{ color: '#38bdf8', fontWeight: 700, fontSize: '0.78rem' }}>
                          ML ETA: {mlEtaTimeStr}
                        </span>
                        {dInfo?.eta_updated && (
                          <span className="eta-updated-badge">
                            ETA UPDATED
                          </span>
                        )}
                      </div>

                      {/* Previous -> Current Transition Display e.g. Gwalior 20:04 -> 20:13 */}
                      {dInfo?.previous_eta && dInfo?.previous_eta !== (dInfo.predicted_eta || dInfo.dynamic_eta) && (
                        <div className="eta-shift-indicator">
                          {formatTime(dInfo.previous_eta)} &rarr; {mlEtaTimeStr}
                        </div>
                      )}

                      {/* Update reason if available */}
                      {dInfo?.update_reason && dInfo?.eta_updated && (
                        <div style={{ fontSize: '0.62rem', color: '#6ee7b7', marginTop: '0.1rem', fontStyle: 'italic' }}>
                          Reason: {dInfo.update_reason}
                        </div>
                      )}

                      {/* Contributing Factors Breakdown (if station has explanation) */}
                      {dInfo?.explanation?.contributing_factors?.length > 0 && dInfo?.eta_updated && (
                        <div style={{ marginTop: '0.25rem', display: 'flex', flexDirection: 'column', gap: '0.15rem' }}>
                          {dInfo.explanation.contributing_factors.map((f, fIdx) => (
                            <div key={fIdx} style={{ fontSize: '0.6rem', color: '#cbd5e1' }}>
                              <span className={`factor-tag ${f.category}`} style={{ fontSize: '0.55rem', padding: '0px 3px' }}>
                                {f.category}
                              </span>
                              {f.impact_description}
                            </div>
                          ))}
                        </div>
                      )}

                      {baseEtaTimeStr && (
                        <div style={{ color: '#94a3b8', fontSize: '0.68rem', marginTop: '0.15rem' }}>
                          Base: {baseEtaTimeStr}
                          {diffMins !== undefined && (
                            <span style={{ 
                              marginLeft: '0.3rem',
                              color: diffMins < 0 ? '#34d399' : diffMins > 0 ? '#f87171' : '#cbd5e1',
                              fontWeight: 600
                            }}>
                              ({diffMins > 0 ? `+${diffMins}m` : `${diffMins}m`})
                            </span>
                          )}
                        </div>
                      )}
                    </div>
                  )}

                  {!isPassed && !mlEtaTimeStr && baseEtaTimeStr && (
                    <span style={{ color: '#38bdf8', fontWeight: 600 }}>
                      ETA: {baseEtaTimeStr}
                    </span>
                  )}

                  {isPassed && (
                    <span style={{ color: '#64748b' }}>CLEARED</span>
                  )}
                </div>

                {/* Range and Confidence */}
                {!isPassed && (
                  <div style={{ marginTop: '0.25rem', fontSize: '0.66rem', color: '#cbd5e1', fontFamily: 'var(--font-mono)' }}>
                    {lowerTimeStr && upperTimeStr && (
                      <div style={{ color: '#a5b4fc' }}>
                        Range: {lowerTimeStr} - {upperTimeStr}
                      </div>
                    )}
                    {dInfo?.confidence !== undefined && dInfo.confidence !== null && (
                      <div style={{ color: '#93c5fd', marginTop: '0.1rem' }}>
                        Conf: {(dInfo.confidence * 100).toFixed(0)}%
                      </div>
                    )}
                  </div>
                )}

                <div className="step-metrics">
                  <span>{stop.distance_from_origin_km} km</span>
                  {!isPassed && (dInfo?.predicted_delay_minutes !== undefined || bInfo?.baseline_delay_minutes !== undefined) && (
                    <span style={{ 
                      color: (dInfo?.predicted_delay_minutes ?? bInfo?.baseline_delay_minutes ?? 0) <= 5 ? '#22c55e' : (dInfo?.predicted_delay_minutes ?? bInfo?.baseline_delay_minutes ?? 0) <= 30 ? '#f59e0b' : '#ef4444',
                      fontWeight: 600
                    }}>
                      Delay: {dInfo?.predicted_delay_minutes !== undefined ? `+${dInfo.predicted_delay_minutes}m` : `+${bInfo.baseline_delay_minutes}m`}
                    </span>
                  )}
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
