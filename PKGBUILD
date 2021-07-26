# Maintainer: Bruno Goncalves <bigbruno@gmail.com>

pkgname=biglinux-improve-compatibility
pkgver=1.$(date +"%Y.%m.%d")
pkgrel=0
arch=('any')
license=('GPL')
depends=('bash')
makedepends=('git')
url="https://gitlab.com/biglinux/biglinux-improve-compatibility"
pkgdesc="Compatibility improvements to make it easier to use packages compiled through the AUR"
source=("git+https://gitlab.com/biglinux/biglinux-improve-compatibility.git")
md5sums=(SKIP)
install=biglinux-improve-compatibility.install

package() {
	cp -R "${srcdir}/biglinux-improve-compatibility/biglinux-improve-compatibility/usr" "${pkgdir}/usr"
}


