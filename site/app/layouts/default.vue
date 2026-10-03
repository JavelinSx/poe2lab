<template>
  <div class="site">
    <SiteSprite />
    <SiteHeader />
    <main><slot /></main>
    <SiteFooter />
    <MobileNav />
    <Toasts />
  </div>
</template>
