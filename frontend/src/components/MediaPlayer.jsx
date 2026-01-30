import React, { useRef, useEffect } from 'react';
import { X, Play, Pause, Volume2, VolumeX, SkipBack, SkipForward } from 'lucide-react';
import './MediaPlayer.css';

const MediaPlayer = ({ mediaUrl, fileName, startTime, onClose }) => {
  const videoRef = useRef(null);
  const hasSeekedRef = useRef(false);
  const [isPlaying, setIsPlaying] = React.useState(false);
  const [isMuted, setIsMuted] = React.useState(false);
  const [currentTime, setCurrentTime] = React.useState(0);
  const [duration, setDuration] = React.useState(0);

  console.log('MediaPlayer received startTime:', startTime, 'type:', typeof startTime);

  // Handle initial seek to startTime
  useEffect(() => {
    const video = videoRef.current;
    if (!video || !startTime || startTime <= 0 || hasSeekedRef.current) return;

    const attemptSeek = () => {
      // Check if the video is seekable at the desired time
      if (video.seekable.length > 0) {
        const seekableEnd = video.seekable.end(video.seekable.length - 1);
        console.log('Video seekable range:', 0, 'to', seekableEnd, 'target:', startTime);
        
        if (startTime <= seekableEnd) {
          console.log('Seeking to:', startTime);
          hasSeekedRef.current = true;
          
          // Use seeked event to confirm seek completed
          const handleSeeked = () => {
            console.log('Seek completed. currentTime:', video.currentTime);
            video.play().then(() => {
              console.log('Playing from:', video.currentTime);
              setIsPlaying(true);
            }).catch(err => {
              console.error('Failed to play:', err);
            });
            video.removeEventListener('seeked', handleSeeked);
          };
          
          video.addEventListener('seeked', handleSeeked);
          video.currentTime = startTime;
        } else {
          console.log('Target time not in seekable range yet, waiting...');
          setTimeout(attemptSeek, 500); // Retry after 500ms
        }
      } else {
        console.log('No seekable ranges yet, waiting...');
        setTimeout(attemptSeek, 500); // Retry after 500ms
      }
    };

    const handleCanPlay = () => {
      console.log('Video can play, attempting seek...');
      attemptSeek();
    };

    if (video.readyState >= 3) {
      // Already ready
      attemptSeek();
    } else {
      video.addEventListener('canplay', handleCanPlay, { once: true });
    }
    
    return () => {
      video.removeEventListener('canplay', handleCanPlay);
    };
  }, [startTime]);

  const formatTime = (seconds) => {
    if (!seconds || isNaN(seconds)) return '0:00';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const handlePlayPause = () => {
    if (videoRef.current) {
      if (isPlaying) {
        videoRef.current.pause();
      } else {
        videoRef.current.play();
      }
      setIsPlaying(!isPlaying);
    }
  };

  const handleMuteToggle = () => {
    if (videoRef.current) {
      videoRef.current.muted = !isMuted;
      setIsMuted(!isMuted);
    }
  };

  const handleTimeUpdate = () => {
    if (videoRef.current) {
      setCurrentTime(videoRef.current.currentTime);
    }
  };

  const handleLoadedMetadata = () => {
    if (videoRef.current) {
      setDuration(videoRef.current.duration);
      console.log('Video duration:', videoRef.current.duration);
    }
  };

  const handleSkip = (seconds) => {
    const video = videoRef.current;
    if (video) {
      const newTime = Math.max(0, Math.min(video.currentTime + seconds, duration));
      console.log(`Skipping ${seconds}s: ${video.currentTime} -> ${newTime}`);
      video.currentTime = newTime;
    } else {
      console.error('Video ref not available for skip');
    }
  };

  const handleSeek = (e) => {
    if (videoRef.current) {
      const rect = e.currentTarget.getBoundingClientRect();
      const percent = (e.clientX - rect.left) / rect.width;
      videoRef.current.currentTime = percent * duration;
    }
  };

  return (
    <div className="media-player-overlay" onClick={onClose}>
      <div className="media-player-container" onClick={(e) => e.stopPropagation()}>
        <div className="media-player-header">
          <h3>{fileName}</h3>
          <button className="close-button" onClick={onClose}>
            <X size={24} />
          </button>
        </div>

        <div className="media-player-content">
          <video
            ref={videoRef}
            src={mediaUrl}
            preload="auto"
            onTimeUpdate={handleTimeUpdate}
            onLoadedMetadata={handleLoadedMetadata}
            onEnded={() => setIsPlaying(false)}
            className="media-player-video"
          />

          <div className="media-player-controls">
            <button className="control-button" onClick={handlePlayPause}>
              {isPlaying ? <Pause size={20} /> : <Play size={20} />}
            </button>

            <button className="control-button" onClick={() => handleSkip(-10)} title="Rewind 10s">
              <SkipBack size={18} />
            </button>

            <button className="control-button" onClick={() => handleSkip(10)} title="Forward 10s">
              <SkipForward size={18} />
            </button>

            <div className="time-display">
              {formatTime(currentTime)} / {formatTime(duration)}
            </div>

            <div className="progress-bar" onClick={handleSeek}>
              <div
                className="progress-fill"
                style={{ width: `${(currentTime / duration) * 100}%` }}
              />
            </div>

            <button className="control-button" onClick={handleMuteToggle}>
              {isMuted ? <VolumeX size={20} /> : <Volume2 size={20} />}
            </button>
          </div>
        </div>

        <div className="media-player-info">
          <p>Started at: {formatTime(startTime)}</p>
        </div>
      </div>
    </div>
  );
};

export default MediaPlayer;
