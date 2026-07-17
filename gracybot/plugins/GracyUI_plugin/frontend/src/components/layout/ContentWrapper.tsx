import type { ReactNode } from 'react';

interface ContentWrapperProps {
  children: ReactNode;
}

export default function ContentWrapper({ children }: ContentWrapperProps) {
  return (
    <main className="pt-[60px] lg:pl-[240px] min-h-screen">
      <div className="p-4 md:p-6 lg:p-8 max-w-7xl mx-auto">
        {children}
      </div>
    </main>
  );
}
