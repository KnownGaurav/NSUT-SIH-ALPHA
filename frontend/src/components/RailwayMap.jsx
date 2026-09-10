import React, { useEffect, useRef } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

export default function RailwayMap({ routeData, livePosition, trainInfo }) {
  const mapContainerRef = useRef(null)
  const mapInstanceRef = useRef(null)
  const layersGroupRef = useRef(null)

  // 1. Initialize Map instance once
  useEffect(() => {
    if (!mapContainerRef.current) return

    if (!mapInstanceRef.current) {
      const map = L.map(mapContainerRef.current, {
        center: [25.5, 82.5],
        zoom: 6,
        zoomControl: true,
        attributionControl: false
      })

      // Industrial dark basemap without watermark (Esri World Dark Gray Canvas)
      L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}', {
        maxZoom: 16,
        attribution: '&copy; Esri, HERE, Garmin &bull; IR Telemetry'
      }).addTo(map)

      // Boundaries & labels overlay
      L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}', {
        maxZoom: 16,
        pane: 'tilePane'
      }).addTo(map)

      layersGroupRef.current = L.featureGroup().addTo(map)
      mapInstanceRef.current = map
    }

    return () => {
      // Map cleanup on unmount
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove()
        mapInstanceRef.current = null
      }
    }
  }, [])

  // 2. Render Route, Stations, and Train Position when data updates
  useEffect(() => {
    const map = mapInstanceRef.current
    const group = layersGroupRef.current
    if (!map || !group) return

    // Clear previous vector layers
    group.clearLayers()

    const stops = routeData?.stops || []
    if (stops.length === 0) return

    const coordinates = stops.map(s => [s.latitude, s.longitude])

    // Find current position index in route
    let currentStopIndex = -1
    if (livePosition?.current_station) {
      currentStopIndex = stops.findIndex(s => s.station_code === livePosition.current_station)
    }

    // A. Draw Route Polylines:
    // Split into passed track (dimmed) and upcoming track (solid high-contrast)
    if (currentStopIndex >= 0 && currentStopIndex < stops.length - 1 && livePosition) {
      const passedCoords = coordinates.slice(0, currentStopIndex + 1)
      passedCoords.push([livePosition.latitude, livePosition.longitude])

      const upcomingCoords = [[livePosition.latitude, livePosition.longitude], ...coordinates.slice(currentStopIndex + 1)]

      // Passed section: dashed muted line
      const passedLine = L.polyline(passedCoords, {
        color: '#64748b',
        weight: 3,
        dashArray: '5, 6',
        opacity: 0.7
      })
      group.addLayer(passedLine)

      // Upcoming section: solid high-visibility railway track line
      const upcomingLine = L.polyline(upcomingCoords, {
        color: '#38bdf8',
        weight: 4,
        opacity: 0.95
      })
      group.addLayer(upcomingLine)
    } else {
      // Entire route track
      const fullLine = L.polyline(coordinates, {
        color: '#38bdf8',
        weight: 3.5,
        opacity: 0.9
      })
      group.addLayer(fullLine)
    }

    // B. Draw Station Markers
    stops.forEach((stop, idx) => {
      const isPassed = currentStopIndex >= 0 && idx <= currentStopIndex
      const isOrigin = idx === 0
      const isDestination = idx === stops.length - 1

      const markerColor = isOrigin || isDestination ? '#f8fafc' : isPassed ? '#64748b' : '#38bdf8'
      const markerRadius = isOrigin || isDestination ? 7 : 5

      const circle = L.circleMarker([stop.latitude, stop.longitude], {
        radius: markerRadius,
        fillColor: markerColor,
        color: '#0f172a',
        weight: 2,
        fillOpacity: 1
      })

      // Station tooltip
      circle.bindTooltip(
        `<div style="font-family: monospace; font-size: 11px;">
          <strong>${stop.station_code}</strong> - ${stop.station_name}<br/>
          <span>Seq: ${stop.sequence} &bull; Dist: ${stop.distance_from_origin_km} km</span><br/>
          <span>Sched Arr: ${stop.scheduled_arrival || 'Origin'} &bull; Dep: ${stop.scheduled_departure || 'Term'}</span>
        </div>`,
        { direction: 'top', offset: [0, -6], className: 'station-tooltip' }
      )

      group.addLayer(circle)
    })

    // C. Draw Current Train Live Position Marker (Only if it matches the current selected train)
    const matchesCurrentTrain = !trainInfo?.train_number || !livePosition?.train_number || (trainInfo.train_number === livePosition.train_number)
    if (matchesCurrentTrain && livePosition?.latitude && livePosition?.longitude) {
      const delayStatus = livePosition.delay_status || 'on_time'
      let statusColor = '#16a34a' // Green (on-time)
      if (delayStatus === 'moderate') statusColor = '#d97706' // Amber (5-30m)
      if (delayStatus === 'severe') statusColor = '#dc2626'   // Red (>30m)

      const trainIcon = L.divIcon({
        className: 'train-marker-container',
        html: `
          <div style="position: relative; width: 34px; height: 34px; display: flex; align-items: center; justify-content: center;">
            <div style="position: absolute; width: 30px; height: 30px; border-radius: 50%; background-color: ${statusColor}; opacity: 0.25; animation: pulse-ring 2s infinite;"></div>
            <div style="position: relative; width: 22px; height: 22px; border-radius: 50%; background-color: ${statusColor}; border: 2px solid #ffffff; display: flex; align-items: center; justify-content: center; box-shadow: 0 0 10px rgba(0,0,0,0.6);">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <rect width="16" height="16" x="4" y="3" rx="2"/>
                <path d="M4 11h16"/>
                <path d="M12 3v8"/>
                <path d="m8 19-2 3"/>
                <path d="m18 22-2-3"/>
                <circle cx="8" cy="15" r="1"/>
                <circle cx="16" cy="15" r="1"/>
              </svg>
            </div>
            <div style="position: absolute; top: 26px; white-space: nowrap; background: #0b0e14; border: 1px solid #334155; color: #f8fafc; font-size: 10px; font-weight: 700; font-family: monospace; padding: 1px 4px; border-radius: 2px;">
              ${livePosition.train_number}
            </div>
          </div>
        `,
        iconSize: [34, 34],
        iconAnchor: [17, 17]
      })

      const trainMarker = L.marker([livePosition.latitude, livePosition.longitude], {
        icon: trainIcon,
        zIndexOffset: 1000
      })

      trainMarker.bindPopup(`
        <div style="font-family: monospace; font-size: 11px; padding: 2px;">
          <strong style="color: #38bdf8;">TRAIN ${livePosition.train_number}</strong><br/>
          <span>Speed: <strong>${livePosition.speed_kmh} km/h</strong></span><br/>
          <span>Delay: <strong style="color: ${statusColor};">${livePosition.current_delay_minutes} mins</strong></span><br/>
          <span>Section: ${livePosition.current_station || '--'} &rarr; ${livePosition.next_station || '--'}</span><br/>
          <span>Source: <strong>${livePosition.data_source}</strong></span>
        </div>
      `)

      group.addLayer(trainMarker)
    }

    // D. Fit bounds so the full route is framed
    const allCoords = [...coordinates]
    if (livePosition?.latitude && livePosition?.longitude) {
      allCoords.push([livePosition.latitude, livePosition.longitude])
    }
    if (allCoords.length > 0) {
      map.fitBounds(L.latLngBounds(allCoords), {
        padding: [45, 45],
        maxZoom: 10
      })
    }
  }, [routeData, livePosition])

  return (
    <div 
      ref={mapContainerRef} 
      style={{ 
        width: '100%', 
        height: '100%', 
        minHeight: '480px',
        backgroundColor: '#090d14',
        position: 'relative'
      }} 
    />
  )
}
