import React, { useState } from 'react';
import { Button } from '@/components/livekit/button';

export const WelcomeView = React.forwardRef<HTMLDivElement, any>(
  ({ startButtonText, onStartCall }, ref) => {
    const [name, setName] = useState('');
    const [started, setStarted] = useState(false);

    async function handleStart() {
      setStarted(true);
      onStartCall?.(name.trim());
    }

    return (
      <div
        ref={ref}
        className="min-h-screen w-full flex flex-col justify-center 
        items-center md:items-end md:pr-24 lg:pr-32 bg-transparent text-gray-900"
      >
        <div className="absolute left-0 top-1/2 -translate-y-1/2 w-[60%] md:w-[45%] lg:w-[40%] 
        pl-10 pr-10 pointer-events-none flex items-center">
          <h1
          className="
          text-[10vw] md:text-[6vw] lg:text-[5vw]
          font-extrabold text-gray-900 leading-tight
          whitespace-normal break-words select-none
          "
          >
      Voice Improv Battle
          </h1>
        </div>
        <h6 className="text-gray-600 text-sm max-w-xs leading-relaxed">
          By Piyush Kopte
        </h6>

        {!started && (
          <section
            className="
              relative flex flex-col items-center text-center p-10
              w-full max-w-sm mx-4 md:mx-0
              rounded-3xl backdrop-blur-xl border border-gray-300/40
              bg-white shadow-[0_0_40px_rgba(147,51,234,0.15)]
              animate-[fadeSlide_0.9s_ease-out]
            "
          >
            {/* Decorative Lights */}
            <div className="absolute -top-4 -left-4 w-20 h-20 bg-purple-300/40 blur-3xl rounded-full pointer-events-none"></div>
            <div className="absolute bottom-0 right-0 w-24 h-24 bg-blue-300/40 blur-3xl rounded-full pointer-events-none"></div>

            {/* Icon */}
            <div className="text-5xl mb-6">
              🎮
            </div>

            <h2 className="text-3xl font-bold tracking-tight mb-2">
              Welcome to the Arena
            </h2>
            <p className="text-gray-600 text-sm max-w-xs leading-relaxed">
              Enter your name and begin your quest.
            </p>

            {/* Input Section */}
            <div className="mt-8 w-full">
              <label className="block text-xs font-bold uppercase tracking-wider mb-2 text-left text-gray-600 ml-1">
                Your Name
              </label>

              <div className="flex items-stretch gap-2">
                <input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleStart()}
                  placeholder="Type your name..."
                  className="
                    flex-1 rounded-xl px-4 py-3 font-semibold
                    bg-white text-gray-900 placeholder:text-gray-400
                    border border-gray-300
                    focus:ring-2 focus:ring-purple-400/50 transition-all
                  "
                />

                <Button
                  onClick={handleStart}
                  className="
                    px-6 rounded-xl font-bold uppercase
                    bg-gradient-to-r from-purple-500 to-pink-500 text-white
                    shadow-lg hover:scale-[1.03] active:scale-95 transition-all
                  "
                >
                  Go →
                </Button>
              </div>
            </div>

            <div className="mt-4 text-[10px] text-gray-500 uppercase tracking-widest font-mono">
              Press Enter to Start
            </div>
          </section>
        )}

        {started && (
          <div className="text-center text-gray-900 text-2xl font-bold animate-pulse md:pr-12">
            ⚡ Preparing your adventure…
          </div>
        )}
      </div>
    );
  }
);

WelcomeView.displayName = 'WelcomeView';
