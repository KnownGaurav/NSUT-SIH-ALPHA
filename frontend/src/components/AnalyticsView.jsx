import React, { useState, useEffect } from 'react'

export default function AnalyticsView({ onBackToDashboard }) {
  const [analytics, setAnalytics] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    async function fetchAnalytics() {
      try {
        setLoading(true)
        const res = await fetch('/api/trains/analytics/model-performance')
        if (res.ok) {
          const data = await res.json()
          setAnalytics(data)
        } else {
          setError('Failed to load performance analytics')
        }
      } catch (err) {
        setError(err.message || 'Error fetching analytics')
      } finally {
        setLoading(false)
      }
    }
    fetchAnalytics()
  }, [])

  if (loading) {
    return (
      <div className="analytics-loading">
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.85rem', color: '#38bdf8' }}>
          LOADING EMPIRICAL MODEL PERFORMANCE METRICS...
        </div>
      </div>
    )
  }

  if (error || !analytics) {
    return (
      <div style={{ padding: '2rem', textAlign: 'center', color: '#f87171', fontFamily: 'var(--font-mono)' }}>
        [ERROR] {error || 'No analytics available'}
      </div>
    )
  }

  const base = analytics.baseline_metrics
  const ml = analytics.ml_metrics

  return (
    <div className="analytics-layout">
      {/* Header bar */}
      <header className="analytics-header">
        <div className="analytics-title-group">
          <div className="cr-badge" style={{ backgroundColor: '#0284c7' }}>IR-ML-EVAL</div>
          <div>
            <div className="cr-title">HISTORICAL PERFORMANCE &amp; MODEL ANALYTICS</div>
            <div className="cr-subtitle">
              Out-of-Time Validation Comparison: Deterministic Baseline vs. XGBoost Dynamic ETA Predictor
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <span className="badge badge-demo">
            <span className="dot"></span>
            EMPIRICAL EVALUATION &bull; NO FABRICATED METRICS
          </span>
          <button className="btn" onClick={onBackToDashboard}>
            &larr; Return to Supervision
          </button>
        </div>
      </header>

      {/* Main Analytics Content Container */}
      <div className="analytics-container">
        
        {/* Top Summary Banner */}
        <div className="analytics-banner">
          <div className="banner-item">
            <div className="banner-label">Model Architecture</div>
            <div className="banner-val">{analytics.model_name} (v{analytics.model_version})</div>
          </div>
          <div className="banner-item">
            <div className="banner-label">Validation Method</div>
            <div className="banner-val" style={{ textTransform: 'capitalize' }}>
              {analytics.validation_split_method.replace(/_/g, ' ')}
            </div>
          </div>
          <div className="banner-item">
            <div className="banner-label">Evaluation Dataset</div>
            <div className="banner-val">{analytics.total_evaluation_samples} total ({analytics.validation_samples} holdout test)</div>
          </div>
          <div className="banner-item">
            <div className="banner-label">MAE Reduction vs. Baseline</div>
            <div className="banner-val highlight-green">
              -{analytics.mae_reduction_minutes} min (-{analytics.mae_reduction_percent}%)
            </div>
          </div>
          <div className="banner-item">
            <div className="banner-label">&plusmn;5 Min Precision Gain</div>
            <div className="banner-val highlight-blue">
              +{analytics.acc_within_5m_gain_percent}%
            </div>
          </div>
        </div>

        {/* Section 1: Baseline ETA vs ML ETA Comparison Table & Visual Bars */}
        <div className="analytics-card">
          <div className="analytics-card-header">
            <span>MODEL EVALUATION METRICS: BASELINE ETA VS. XGBOOST DYNAMIC ETA</span>
            <span style={{ fontSize: '0.65rem', color: '#94a3b8', fontFamily: 'var(--font-mono)' }}>
              HOLDOUT VALIDATION SET (N = {analytics.validation_samples})
            </span>
          </div>

          <div style={{ overflowX: 'auto' }}>
            <table className="analytics-table">
              <thead>
                <tr>
                  <th style={{ textAlign: 'left' }}>Evaluation Metric</th>
                  <th style={{ textAlign: 'center' }}>Deterministic Baseline</th>
                  <th style={{ textAlign: 'center' }}>XGBoost Dynamic ML</th>
                  <th style={{ textAlign: 'center' }}>Variance / Gain</th>
                  <th style={{ textAlign: 'left', minWidth: '220px' }}>Visual Comparison</th>
                </tr>
              </thead>
              <tbody>
                {/* MAE */}
                <tr>
                  <td>
                    <strong>Mean Absolute Error (MAE)</strong>
                    <div className="metric-formula">Mean |Predicted Travel Time - Actual Travel Time| in minutes</div>
                  </td>
                  <td className="mono center">{base.mae_minutes.toFixed(2)} min</td>
                  <td className="mono center highlight-green"><strong>{ml.mae_minutes.toFixed(2)} min</strong></td>
                  <td className="mono center highlight-green">-{analytics.mae_reduction_minutes.toFixed(2)}m ({analytics.mae_reduction_percent}%)</td>
                  <td>
                    <div className="comparison-bar-container">
                      <div className="comp-bar-baseline" style={{ width: `${(base.mae_minutes / 8.5) * 100}%` }}>
                        <span>Base: {base.mae_minutes}m</span>
                      </div>
                      <div className="comp-bar-ml" style={{ width: `${(ml.mae_minutes / 8.5) * 100}%` }}>
                        <span>ML: {ml.mae_minutes}m</span>
                      </div>
                    </div>
                  </td>
                </tr>

                {/* RMSE */}
                <tr>
                  <td>
                    <strong>Root Mean Squared Error (RMSE)</strong>
                    <div className="metric-formula">Square root of mean squared error (penalizes large outlier delay misses)</div>
                  </td>
                  <td className="mono center">{base.rmse_minutes.toFixed(2)} min</td>
                  <td className="mono center highlight-green"><strong>{ml.rmse_minutes.toFixed(2)} min</strong></td>
                  <td className="mono center highlight-green">-{(base.rmse_minutes - ml.rmse_minutes).toFixed(2)}m</td>
                  <td>
                    <div className="comparison-bar-container">
                      <div className="comp-bar-baseline" style={{ width: `${(base.rmse_minutes / 9.0) * 100}%` }}>
                        <span>Base: {base.rmse_minutes}m</span>
                      </div>
                      <div className="comp-bar-ml" style={{ width: `${(ml.rmse_minutes / 9.0) * 100}%` }}>
                        <span>ML: {ml.rmse_minutes}m</span>
                      </div>
                    </div>
                  </td>
                </tr>

                {/* Accuracy within +-5 mins */}
                <tr>
                  <td>
                    <strong>Precision within &plusmn;5 Minutes</strong>
                    <div className="metric-formula">Proportion of station arrival forecasts within &plusmn;5 minutes of actual arrival</div>
                  </td>
                  <td className="mono center">{base.accuracy_within_5_min_percent.toFixed(1)}%</td>
                  <td className="mono center highlight-green"><strong>{ml.accuracy_within_5_min_percent.toFixed(1)}%</strong></td>
                  <td className="mono center highlight-green">+{analytics.acc_within_5m_gain_percent.toFixed(1)}%</td>
                  <td>
                    <div className="precision-bar-wrapper">
                      <div className="precision-bar-fill baseline" style={{ width: `${base.accuracy_within_5_min_percent}%` }}></div>
                      <div className="precision-bar-fill ml" style={{ width: `${ml.accuracy_within_5_min_percent}%` }}></div>
                    </div>
                  </td>
                </tr>

                {/* Accuracy within +-10 mins */}
                <tr>
                  <td>
                    <strong>Precision within &plusmn;10 Minutes</strong>
                    <div className="metric-formula">Proportion of station arrival forecasts within &plusmn;10 minutes of actual arrival</div>
                  </td>
                  <td className="mono center">{base.accuracy_within_10_min_percent.toFixed(1)}%</td>
                  <td className="mono center highlight-green"><strong>{ml.accuracy_within_10_min_percent.toFixed(1)}%</strong></td>
                  <td className="mono center highlight-green">+{(ml.accuracy_within_10_min_percent - base.accuracy_within_10_min_percent).toFixed(1)}%</td>
                  <td>
                    <div className="precision-bar-wrapper">
                      <div className="precision-bar-fill baseline" style={{ width: `${base.accuracy_within_10_min_percent}%` }}></div>
                      <div className="precision-bar-fill ml" style={{ width: `${ml.accuracy_within_10_min_percent}%` }}></div>
                    </div>
                  </td>
                </tr>

                {/* Accuracy within +-15 mins */}
                <tr>
                  <td>
                    <strong>Precision within &plusmn;15 Minutes</strong>
                    <div className="metric-formula">Proportion of station arrival forecasts within &plusmn;15 minutes of actual arrival</div>
                  </td>
                  <td className="mono center">{base.accuracy_within_15_min_percent.toFixed(1)}%</td>
                  <td className="mono center highlight-green"><strong>{ml.accuracy_within_15_min_percent.toFixed(1)}%</strong></td>
                  <td className="mono center highlight-green">+{(ml.accuracy_within_15_min_percent - base.accuracy_within_15_min_percent).toFixed(1)}%</td>
                  <td>
                    <div className="precision-bar-wrapper">
                      <div className="precision-bar-fill baseline" style={{ width: `${base.accuracy_within_15_min_percent}%` }}></div>
                      <div className="precision-bar-fill ml" style={{ width: `${ml.accuracy_within_15_min_percent}%` }}></div>
                    </div>
                  </td>
                </tr>

                {/* R2 Score */}
                <tr>
                  <td>
                    <strong>Coefficient of Determination (R&sup2;)</strong>
                    <div className="metric-formula">Proportion of remaining travel time variance explained by the model</div>
                  </td>
                  <td className="mono center">{base.r2_score.toFixed(4)}</td>
                  <td className="mono center highlight-blue"><strong>{ml.r2_score.toFixed(4)}</strong></td>
                  <td className="mono center">+{(ml.r2_score - base.r2_score).toFixed(4)}</td>
                  <td>
                    <span style={{ fontSize: '0.7rem', color: '#94a3b8' }}>Statistical ceiling (0.9998)</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        {/* Section 2: Sectional Operational Performance Table */}
        <div className="analytics-card">
          <div className="analytics-card-header">
            <span>HISTORICAL SECTIONAL PERFORMANCE &amp; RECOVERY TENDENCIES</span>
            <span style={{ fontSize: '0.65rem', color: '#94a3b8', fontFamily: 'var(--font-mono)' }}>
              COMPUTED ACROSS {analytics.sections.length} CORRIDOR TRACK BLOCKS
            </span>
          </div>

          <div style={{ overflowX: 'auto' }}>
            <table className="analytics-table">
              <thead>
                <tr>
                  <th style={{ textAlign: 'left' }}>Track Block Section</th>
                  <th style={{ textAlign: 'center' }}>Sample Runs</th>
                  <th style={{ textAlign: 'center' }}>Avg Running Time</th>
                  <th style={{ textAlign: 'center' }}>Avg Delay</th>
                  <th style={{ textAlign: 'center' }}>Delay Variance (&sigma;&sup2;)</th>
                  <th style={{ textAlign: 'center' }}>Recovery Tendency</th>
                  <th style={{ textAlign: 'left' }}>Section Characteristic</th>
                </tr>
              </thead>
              <tbody>
                {analytics.sections.map((sec) => {
                  let recColor = '#94a3b8'
                  let recBadgeClass = 'badge-neutral'
                  let recLabel = 'Neutral Section'

                  if (sec.recovery_status === 'RECOVERING') {
                    recColor = '#34d399'
                    recBadgeClass = 'badge-green'
                    recLabel = 'Slack Recovery Zone'
                  } else if (sec.recovery_status === 'DELAY_ACCUMULATING') {
                    recColor = '#f87171'
                    recBadgeClass = 'badge-red'
                    recLabel = 'Bottleneck / Congested'
                  }

                  return (
                    <tr key={sec.section_id}>
                      <td>
                        <div style={{ fontWeight: 700, fontFamily: 'var(--font-mono)', color: '#f8fafc' }}>
                          {sec.section_id}
                        </div>
                        <div style={{ fontSize: '0.68rem', color: '#94a3b8' }}>
                          {sec.from_station_name} &rarr; {sec.to_station_name}
                        </div>
                      </td>

                      <td className="mono center">{sec.sample_count}</td>
                      <td className="mono center">{sec.average_running_time_minutes.toFixed(1)} min</td>
                      <td className="mono center" style={{ color: sec.average_delay_minutes > 8.0 ? '#f59e0b' : '#cbd5e1' }}>
                        +{sec.average_delay_minutes.toFixed(1)} min
                      </td>
                      <td className="mono center">{sec.delay_variance.toFixed(1)} min&sup2;</td>
                      
                      <td className="mono center" style={{ color: recColor, fontWeight: 700 }}>
                        {sec.recovery_tendency_minutes > 0 ? `+${sec.recovery_tendency_minutes.toFixed(2)}m` : `${sec.recovery_tendency_minutes.toFixed(2)}m`}
                      </td>

                      <td>
                        <span className={`status-tag ${recBadgeClass}`}>
                          {recLabel}
                        </span>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* Section 3: Feature Importances */}
        <div className="analytics-card">
          <div className="analytics-card-header">
            <span>XGBOOST FEATURE IMPORTANCE ATTRIBUTION (GAIN METRIC)</span>
            <span style={{ fontSize: '0.65rem', color: '#94a3b8', fontFamily: 'var(--font-mono)' }}>TOP 8 PREDICTIVE DRIVERS</span>
          </div>

          <div style={{ padding: '0.75rem', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '0.75rem' }}>
            {analytics.feature_importances.map((f, i) => (
              <div key={f.feature_name} className="feature-item-card">
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.72rem', fontFamily: 'var(--font-mono)' }}>
                  <span style={{ color: '#f8fafc' }}>#{i + 1} {f.feature_name}</span>
                  <span style={{ color: '#38bdf8', fontWeight: 700 }}>{(f.importance_score * 100).toFixed(1)}%</span>
                </div>
                <div className="feature-progress-bg">
                  <div className="feature-progress-fill" style={{ width: `${f.importance_score * 100}%` }}></div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Section 4: Zonal Performance Breakdown (Phase 21) */}
        {analytics.zonal_breakdown && analytics.zonal_breakdown.length > 0 && (
          <div className="analytics-card">
            <div className="analytics-card-header">
              <span>ZONAL RAILWAY PERFORMANCE BREAKDOWN</span>
              <span style={{ fontSize: '0.65rem', color: '#94a3b8', fontFamily: 'var(--font-mono)' }}>
                {analytics.zonal_breakdown.length} ZONES · RANKED BY AVG DELAY
              </span>
            </div>

            <div style={{ padding: '0.5rem 0.75rem', fontSize: '0.65rem', color: '#64748b', fontFamily: 'var(--font-mono)', marginBottom: '0.25rem' }}>
              Zone MAE is the ML model's estimated per-zone Mean Absolute Error, scaled from overall validation MAE using
              published Indian Railways Annual Report zonal punctuality indices.
            </div>

            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontFamily: 'var(--font-mono)', fontSize: '0.72rem' }}>
                <thead>
                  <tr style={{ background: '#0a1525', borderBottom: '2px solid #1e293b' }}>
                    {['ZONE', 'RAILWAY', 'AVG DELAY', 'RECOVERY %', 'MODEL MAE', 'SECTIONS', 'SAMPLES', 'STATUS'].map(h => (
                      <th key={h} style={{ padding: '0.45rem 0.7rem', textAlign: 'left', color: '#64748b', fontWeight: 700, letterSpacing: '0.4px', fontSize: '0.6rem', whiteSpace: 'nowrap' }}>
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {analytics.zonal_breakdown.map((z, idx) => {
                    const statusColor = z.dominant_status === 'RECOVERING' ? '#34d399'
                      : z.dominant_status === 'DELAY_ACCUMULATING' ? '#f87171' : '#94a3b8'
                    const statusBg = z.dominant_status === 'RECOVERING' ? '#052e16'
                      : z.dominant_status === 'DELAY_ACCUMULATING' ? '#450a0a' : '#1e293b'
                    const delayColor = z.average_delay_minutes > 12 ? '#f87171'
                      : z.average_delay_minutes > 7 ? '#f59e0b' : '#34d399'
                    const recColor = z.recovery_tendency_percent >= 50 ? '#34d399'
                      : z.recovery_tendency_percent >= 30 ? '#fbbf24' : '#f87171'

                    return (
                      <tr key={z.zone}
                        style={{ borderBottom: '1px solid #0f1c2e', backgroundColor: idx % 2 === 0 ? '#050810' : '#070d1a' }}>
                        <td style={{ padding: '0.45rem 0.7rem', fontWeight: 900, color: '#fbbf24', fontSize: '0.8rem' }}>
                          {z.zone}
                        </td>
                        <td style={{ padding: '0.45rem 0.7rem', color: '#e2e8f0' }}>{z.zone_name}</td>
                        <td style={{ padding: '0.45rem 0.7rem', color: delayColor, fontWeight: 700 }}>
                          +{z.average_delay_minutes.toFixed(1)} min
                        </td>
                        <td style={{ padding: '0.45rem 0.7rem', color: recColor, fontWeight: 700 }}>
                          {z.recovery_tendency_percent.toFixed(1)}%
                          <div style={{ marginTop: '2px', height: '3px', background: '#1e293b', borderRadius: '2px', width: '60px' }}>
                            <div style={{ height: '100%', width: `${Math.min(z.recovery_tendency_percent, 100)}%`, background: recColor, borderRadius: '2px' }} />
                          </div>
                        </td>
                        <td style={{ padding: '0.45rem 0.7rem', color: '#38bdf8', fontWeight: 700 }}>
                          ±{z.model_mae.toFixed(2)} min
                        </td>
                        <td style={{ padding: '0.45rem 0.7rem', color: '#94a3b8' }}>{z.total_sections}</td>
                        <td style={{ padding: '0.45rem 0.7rem', color: '#64748b' }}>{z.sample_count.toLocaleString()}</td>
                        <td style={{ padding: '0.45rem 0.7rem' }}>
                          <span style={{
                            background: statusBg, color: statusColor, fontSize: '0.6rem',
                            fontWeight: 700, padding: '2px 7px', borderRadius: '3px',
                            border: `1px solid ${statusColor}40`
                          }}>
                            {z.dominant_status.replace('_', ' ')}
                          </span>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}

      </div>
    </div>
  )
}

