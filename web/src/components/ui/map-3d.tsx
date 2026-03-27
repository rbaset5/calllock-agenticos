'use client';
import { useRef, useEffect } from 'react';
import mapboxgl from 'mapbox-gl';
import 'mapbox-gl/dist/mapbox-gl.css';

interface Map3DProps {
  lat: number;
  lng: number;
  className?: string;
}

export function Map3D({ lat, lng, className }: Map3DProps) {
  const mapContainer = useRef<HTMLDivElement>(null);
  const map = useRef<mapboxgl.Map | null>(null);

  useEffect(() => {
    if (map.current || !mapContainer.current) return;

    mapboxgl.accessToken = process.env.NEXT_PUBLIC_MAPBOX_ACCESS_TOKEN!;
    const maptilerKey = process.env.NEXT_PUBLIC_MAPTILER_API_KEY;

    map.current = new mapboxgl.Map({
      container: mapContainer.current,
      style: `https://api.maptiler.com/maps/topo-v2/style.json?key=${maptilerKey}`,
      center: [lng, lat],
      zoom: 13,
      pitch: 0,
      bearing: 0,
      interactive: true,
      attributionControl: false,
    });

    new mapboxgl.Marker({ color: '#ef4444', scale: 1 })
      .setLngLat([lng, lat])
      .addTo(map.current);

    return () => {
      map.current?.remove();
      map.current = null;
    };
  }, [lat, lng]);

  return <div ref={mapContainer} className={className} />;
}
