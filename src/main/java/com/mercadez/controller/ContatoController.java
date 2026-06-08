package com.mercadez.controller;

import com.mercadez.dto.ContatoRequest;
import com.mercadez.service.ContatoService;
import jakarta.validation.Valid;
import org.springframework.http.*;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/contato")
public class ContatoController {

    private final ContatoService service;

    public ContatoController(ContatoService service) { this.service = service; }

    /** POST /contato — formulário "Fale Conosco" */
    @PostMapping
    public ResponseEntity<Void> enviar(@Valid @RequestBody ContatoRequest req) {
        service.enviar(req);
        return ResponseEntity.status(HttpStatus.CREATED).build();
    }
}
