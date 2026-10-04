from dataclasses import dataclass, field

from .quote import quote_package


@dataclass
class Shipment:
    origin: str
    destination: str
    service: str = 'standard'
    residential: bool = False
    packages: list = field(default_factory=list)

    def add(self, package):
        self.packages.append(package)
        return self

    def quotes(self):
        return [
            quote_package(package, self.origin, self.destination, self.service, self.residential)
            for package in self.packages
        ]

    def total(self):
        if not self.packages:
            raise ValueError('shipment has no packages')
        return sum(quote.total for quote in self.quotes())
