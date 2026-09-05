<script setup lang="ts">
// The site's mark: a small gold star orbited by three colored stars. On the
// landing page it sits small and mostly still, near the top; the instant a
// request starts, this SAME element grows and glides to the center of the
// screen and starts spinning -- it's the logo becoming the loading
// indicator, not two different graphics swapped out.
withDefaults(defineProps<{ active?: boolean; corner?: boolean }>(), { active: false, corner: false })
</script>

<template>
  <div class="star-logo" :class="{ active, corner }" role="img" aria-label="College Compass">
    <svg viewBox="0 0 120 120" class="orbit">
      <circle cx="60" cy="60" r="7" fill="var(--gold-leaf)" class="center-star" />
      <!--
        Three points spaced 120deg apart around the center, at different
        radii, so the mark reads as a small constellation cluster even at
        rest. Placing them all at the same angle (directly above center,
        stacked only by radius) is what made the idle logo look like a
        stray column of dots instead of an orbit -- rotation still works
        the same from any starting angle since transform-origin is 60,60.
      -->
      <g class="ring">
        <circle cx="60" cy="44" r="4" fill="var(--reach-ember)" />
      </g>
      <g class="ring ring-reverse">
        <circle cx="77.3" cy="70" r="3.5" fill="var(--target-sage)" />
      </g>
      <g class="ring">
        <circle cx="39.2" cy="72" r="3" fill="var(--likely-teal)" />
      </g>
    </svg>
  </div>
</template>

<style scoped>
.star-logo {
  position: fixed;
  left: 50%;
  top: 74px;
  transform: translate(-50%, 0) scale(0.62);
  transition: top 0.7s cubic-bezier(0.65, 0, 0.35, 1), left 0.7s cubic-bezier(0.65, 0, 0.35, 1),
    transform 0.7s cubic-bezier(0.65, 0, 0.35, 1);
  z-index: 20;
  pointer-events: none;
}
.star-logo.active {
  top: 40%;
  transform: translate(-50%, -50%) scale(1.35);
}
/* On the results page the logo tucks into the corner instead of hovering
   over the title -- there's no title there for it to sit above. */
.star-logo.corner {
  left: 28px;
  top: 20px;
  transform: scale(0.48);
  transform-origin: top left;
}
.orbit {
  width: 96px;
  height: 96px;
  display: block;
}
.center-star {
  transform-origin: 60px 60px;
}
.star-logo.active .center-star {
  animation: twinkle 1.6s ease-in-out infinite;
}
.ring {
  transform-origin: 60px 60px;
}
.star-logo.active .ring {
  animation: spin 2.4s linear infinite;
}
.star-logo.active .ring-reverse {
  animation-direction: reverse;
  animation-duration: 1.7s;
}
@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
@keyframes twinkle {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
@media (prefers-reduced-motion: reduce) {
  .star-logo {
    transition: none;
  }
  .star-logo.active .ring,
  .star-logo.active .center-star {
    animation: none;
  }
}
</style>
