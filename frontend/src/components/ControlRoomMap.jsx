import React, { useEffect, useRef } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

export default function ControlRoomMap({ trains = [], selectedTrainNumber, onSelectTrain, allRoutes = {} }) {
  const mapContainerRef = useRef(null)
  const mapInstanceRef = useRef(null)
  const routesLayerGroupRef = useRef(null)
  const markersLayerGroupRef = useRef(null)

  // 1. Initialize Map instance once with pan-India extent
  useEffect(() => {
    if (!mapContainerRef.current) return

    if (!mapInstanceRef.current) {
      const map = L.map(mapContainerRef.current, {
        center: [23.5, 80.0], // Centered on India railway network
        zoom: 5,
        zoomControl: true,
        attributionControl: false
      })

      // Industrial dark basemap without watermark (Esri World Dark Gray Canvas)
      L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}', {
        maxZoom: 16,
        attribution: '&copy; Esri, HERE, Garmin &bull; IR Network Operations'
      }).addTo(map)

      // Boundaries & labels overlay
      L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}', {
        maxZoom: 16,
        pane: 'tilePane'
      }).addTo(map)

      routesLayerGroupRef.current = L.featureGroup().addTo(map)
      markersLayerGroupRef.current = L.featureGroup().addTo(map)
      mapInstanceRef.current = map
    }

    return () => {
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove()
        mapInstanceRef.current = null
      }
    }
  }, [])

  // 2. Draw corridor network tracks
  useEffect(() => {
    const routesGroup = routesLayerGroupRef.current
    if (!routesGroup) return

    routesGroup.clearLayers()

    // Only draw the route polyline for the actively selected train
    // (or trains present in the active filteredTrains roster)
    const activeTrainNumbers = new Set(trains.map(t => t.train_number))
    
    Object.entries(allRoutes).forEach(([tNum, rData]) => {
      // If a train is selected, focus exclusively on the selected train's corridor route!
      if (selectedTrainNumber) {
        if (tNum !== selectedTrainNumber) return
      } else if (!activeTrainNumbers.has(tNum)) {
        return
      }

      const stops = rData?.stops || []
      if (stops.length < 2) return

      const coords = stops.map(s => [s.latitude, s.longitude])
      const isSelected = tNum === selectedTrainNumber

      const line = L.polyline(coords, {
        color: '#38bdf8',
        weight: 3.5,
        opacity: 0.95
      })
      routesGroup.addLayer(line)

      // Draw route stations
      stops.forEach((s) => {
        const stationCircle = L.circleMarker([s.latitude, s.longitude], {
          radius: 3.5,
          fillColor: '#38bdf8',
          color: '#0f172a',
          weight: 1.5,
          fillOpacity: 0.9
        })
        stationCircle.bindTooltip(
          `<div style="font-family: monospace; font-size: 10px;">${s.station_code} - ${s.station_name}</div>`,
          { direction: 'top', className: 'station-tooltip' }
        )
        routesGroup.addLayer(stationCircle)
      })
    })
  }, [allRoutes, selectedTrainNumber, trains])

  // 3. Draw active train markers with operational status colors
  useEffect(() => {
    const markersGroup = markersLayerGroupRef.current
    if (!markersGroup) return

    markersGroup.clearLayers()

    trains.forEach((train) => {
      if (!train.latitude || !train.longitude) return

      const isSelected = train.train_number === selectedTrainNumber

      // Operational Status Colors:
      // Green = On time (<= 5 min)
      // Amber = Moderate delay (5-30 min)
      // Red = Severe delay (> 30 min)
      let statusColor = '#22c55e' // on time
      if (train.delay_status === 'moderate') statusColor = '#f59e0b'
      if (train.delay_status === 'severe') statusColor = '#ef4444'

      const markerHtml = `
        <div style="position: relative; width: 32px; height: 32px; display: flex; align-items: center; justify-content: center; cursor: pointer;">
          ${isSelected ? `
            <div style="position: absolute; width: 34px; height: 34px; border: 2px solid #38bdf8; border-radius: 4px; box-sizing: border-box;"></div>
          ` : ''}
          <div style="width: 20px; height: 20px; background-color: ${statusColor}; border: 2px solid #0f172a; border-radius: 2px; display: flex; align-items: center; justify-content: center; box-shadow: 0 2px 4px rgba(0,0,0,0.8);">
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="#0f172a" stroke-width="2.8" stroke-linecap="round" stroke-linejoin="round">
              <rect width="16" height="16" x="4" y="3" rx="1"/>
              <path d="M4 11h16"/>
              <path d="M12 3v8"/>
              <circle cx="8" cy="15" r="1"/>
              <circle cx="16" cy="15" r="1"/>
            </svg>
          </div>
          <div style="position: absolute; top: 22px; white-space: nowrap; background: #0f172a; border: 1px solid ${isSelected ? '#38bdf8' : '#334155'}; color: ${isSelected ? '#38bdf8' : '#f8fafc'}; font-size: 9px; font-weight: 700; font-family: monospace; padding: 0 3px; border-radius: 2px;">
            ${train.train_number}
          </div>
        </div>
      `

      const icon = L.divIcon({
        className: 'control-room-train-marker',
        html: markerHtml,
        iconSize: [32, 32],
        iconAnchor: [16, 16]
      })

      const marker = L.marker([train.latitude, train.longitude], {
        icon: icon,
        zIndexOffset: isSelected ? 1500 : 500
      })

      marker.on('click', () => {
        if (onSelectTrain) onSelectTrain(train.train_number)
      })

      marker.bindTooltip(`
        <div style="font-family: monospace; font-size: 11px; padding: 2px;">
          <strong style="color: #38bdf8;">${train.train_number}</strong> ${train.train_name}<br/>
          <span>Speed: <strong>${train.speed_kmh} km/h</strong></span><br/>
          <span>Delay: <strong style="color: ${statusColor};">+${train.current_delay_minutes} min (${train.delay_status.toUpperCase()})</strong></span><br/>
          <span>Next: <strong>${train.next_station_name || train.next_station || 'N/A'}</strong></span>
        </div>
      `, { direction: 'top', offset: [0, -10], className: 'station-tooltip' })

      markersGroup.addLayer(marker)
    })
  }, [trains, selectedTrainNumber, onSelectTrain])

  // 4. Focus on selected train if requested
  useEffect(() => {
    if (!selectedTrainNumber || !mapInstanceRef.current) return
    const selTrain = trains.find(t => t.train_number === selectedTrainNumber)
    if (selTrain && selTrain.latitude && selTrain.longitude) {
      mapInstanceRef.current.panTo([selTrain.latitude, selTrain.longitude], { animate: true, duration: 0.6 })
    }
  }, [selectedTrainNumber])

  return (
    <div 
      ref={mapContainerRef} 
      style={{ 
        width: '100%', 
        height: '100%', 
        minHeight: '520px', 
        backgroundColor: '#090d14',
        position: 'relative'
      }} 
    />
  )
}
