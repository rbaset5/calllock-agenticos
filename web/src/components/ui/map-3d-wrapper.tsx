import dynamic from 'next/dynamic';

export const Map3DWrapper = dynamic(
  () => import('./map-3d').then(mod => mod.Map3D),
  {
    ssr: false,
    loading: () => (
      <div className="w-full h-full bg-[#0d1a3a] animate-pulse" />
    )
  }
);
